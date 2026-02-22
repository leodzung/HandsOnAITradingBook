"""Main CLI interface for Agentic Portfolio Manager MVP"""
import os
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich import print as rprint

import config
from models import save_json, load_json
from alpaca_client import AlpacaClient
from llm_client import LLMClient
from orchestrator import Orchestrator


console = Console()


class PortfolioManagerCLI:
    """CLI for interacting with the agentic portfolio manager"""

    def __init__(self):
        config.validate_config()
        self.alpaca = AlpacaClient()
        self.llm = LLMClient()
        self.orchestrator = Orchestrator(self.llm)
        self.portfolio = None
        self.last_report = None
        self.recommendations_file = os.path.join(config.DATA_DIR, 'last_recommendations.json')

    def run(self):
        """Main CLI loop"""
        console.print("\n[bold cyan]🤖 Agentic Portfolio Manager - MVP[/bold cyan]")
        console.print("[dim]Powered by GPT-4 and Alpaca Markets[/dim]\n")

        # Load portfolio
        self.refresh_portfolio()

        while True:
            self.show_menu()
            choice = Prompt.ask("\n[bold]Select option[/bold]", choices=["1", "2", "3", "4", "5", "6"])

            if choice == "1":
                self.run_analysis()
            elif choice == "2":
                self.view_last_report()
            elif choice == "3":
                self.execute_recommendations()
            elif choice == "4":
                self.refresh_portfolio()
            elif choice == "5":
                self.view_market_status()
            elif choice == "6":
                console.print("\n[yellow]Goodbye! 👋[/yellow]\n")
                break

    def show_menu(self):
        """Display main menu"""
        console.print("\n[bold]Current Portfolio Summary:[/bold]")

        if self.portfolio:
            # Create portfolio table
            table = Table(show_header=False, box=None)
            table.add_row("💵 Cash", f"[green]${self.portfolio.cash:,.2f}[/green]")
            table.add_row("📊 Portfolio Value", f"[cyan]${self.portfolio.portfolio_value:,.2f}[/cyan]")
            table.add_row("📈 Positions", f"{len(self.portfolio.positions)}")
            console.print(table)

            if self.portfolio.positions:
                console.print("\n[bold]Positions:[/bold]")
                pos_table = Table()
                pos_table.add_column("Symbol", style="cyan")
                pos_table.add_column("Qty", justify="right")
                pos_table.add_column("Price", justify="right")
                pos_table.add_column("Value", justify="right")
                pos_table.add_column("Cost Basis", justify="right")
                pos_table.add_column("P&L (vs Cost Basis)", justify="right")

                for pos in self.portfolio.positions:
                    # Use original cost basis P&L if available, otherwise Alpaca's P&L
                    if pos.original_cost_basis is not None and pos.original_pl is not None:
                        pl = pos.original_pl
                        pl_pct = pos.original_pl_pct or 0
                        cost_basis_str = f"${pos.original_cost_basis:.2f}"
                    else:
                        pl = pos.unrealized_pl
                        pl_pct = pos.unrealized_pl_pct
                        cost_basis_str = f"${pos.avg_entry_price:.2f}"

                    pl_color = "green" if pl >= 0 else "red"
                    pl_sign = "+" if pl >= 0 else ""
                    pos_table.add_row(
                        pos.symbol,
                        f"{pos.quantity:.2f}",
                        f"${pos.current_price:.2f}",
                        f"${pos.market_value:,.2f}",
                        cost_basis_str,
                        f"[{pl_color}]{pl_sign}${pl:,.2f} ({pl_sign}{pl_pct:.1f}%)[/{pl_color}]"
                    )

                console.print(pos_table)

                # Show total P&L summary
                total_original_pl = sum(
                    pos.original_pl for pos in self.portfolio.positions
                    if pos.original_pl is not None
                )
                total_cost = sum(
                    pos.quantity * pos.original_cost_basis
                    for pos in self.portfolio.positions
                    if pos.original_cost_basis is not None
                )
                if total_cost > 0:
                    total_pl_pct = (total_original_pl / total_cost) * 100
                    pl_color = "green" if total_original_pl >= 0 else "red"
                    pl_sign = "+" if total_original_pl >= 0 else ""
                    console.print(f"\n[bold]Total P&L (vs Robinhood Cost Basis):[/bold] [{pl_color}]{pl_sign}${total_original_pl:,.2f} ({pl_sign}{total_pl_pct:.1f}%)[/{pl_color}]")

        console.print("\n[bold]━━━ Main Menu ━━━[/bold]")
        console.print("1. 🔍 Run AI Analysis")
        console.print("2. 📄 View Last Report")
        console.print("3. ✅ Execute Approved Trades")
        console.print("4. 🔄 Refresh Portfolio")
        console.print("5. 📊 Market Status")
        console.print("6. 🚪 Exit")

    def refresh_portfolio(self):
        """Fetch latest portfolio data"""
        try:
            console.print("\n[dim]Fetching portfolio...[/dim]")
            self.portfolio = self.alpaca.get_portfolio()
            console.print("[green]✓ Portfolio loaded[/green]")
        except Exception as e:
            console.print(f"[red]Error loading portfolio: {e}[/red]")

    def run_analysis(self):
        """Run the agentic analysis"""
        if not self.portfolio:
            console.print("[red]Please refresh portfolio first[/red]")
            return

        console.print("\n[bold yellow]🤖 Starting AI Agent Analysis...[/bold yellow]")
        console.print("[dim]This may take 30-60 seconds...[/dim]\n")

        try:
            # Run analysis
            report = self.orchestrator.run_analysis(self.portfolio)
            self.last_report = report

            # Save report
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_path = os.path.join(config.DATA_DIR, f"report_{timestamp}.md")
            report.save_to_file(report_path)

            # Save JSON for execution
            save_json(report.to_dict(), self.recommendations_file)

            # Display report
            console.print("\n[bold green]✅ Analysis Complete![/bold green]\n")
            self.display_report(report)

            console.print(f"\n[dim]📄 Report saved to: {report_path}[/dim]")

        except Exception as e:
            console.print(f"[red]Error during analysis: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

    def display_report(self, report):
        """Display the recommendation report"""
        # Executive summary
        console.print(Panel(
            report.executive_summary,
            title="[bold]Executive Summary[/bold]",
            border_style="cyan"
        ))

        # Recommended actions
        if report.recommended_actions:
            console.print("\n[bold]📋 Recommended Actions:[/bold]\n")

            for i, action in enumerate(report.recommended_actions, 1):
                action_color = "green" if action['action'] == 'buy' else "red" if action['action'] == 'sell' else "yellow"
                console.print(f"[bold]{i}. [{action_color}]{action['action'].upper()}[/{action_color}] {action['symbol']} - {action['quantity']} shares[/bold]")
                console.print(f"   Conviction: {action['conviction']}/100")
                console.print(f"   Reasoning: {action['reasoning']}")
                console.print(f"   Estimated: ${action.get('estimated_value', 0):,.2f}\n")
        else:
            console.print("\n[yellow]No actions recommended at this time.[/yellow]\n")

        # Risk assessment
        console.print("[bold]⚠️  Risk Assessment:[/bold]")
        risk = report.risk_assessment
        console.print(f"   Status: {risk.get('overall_status', 'Unknown')}")
        if 'key_concerns' in risk and risk['key_concerns']:
            console.print("   Concerns:")
            for concern in risk['key_concerns']:
                console.print(f"     • {concern}")

        console.print(f"\n[bold]Confidence: {report.overall_confidence}/100[/bold]")

    def view_last_report(self):
        """View the last generated report"""
        if not self.last_report:
            # Try to load from file
            try:
                data = load_json(self.recommendations_file)
                if not data:
                    console.print("[yellow]No previous reports found. Run analysis first.[/yellow]")
                    return
                console.print("\n[dim]Loading last report...[/dim]\n")
                # Display from JSON (simplified)
                console.print(f"[bold]Last Report:[/bold] {data.get('timestamp', 'Unknown')}")
                console.print(f"\n{data.get('executive_summary', '')}")
            except Exception as e:
                console.print(f"[red]Error loading report: {e}[/red]")
        else:
            self.display_report(self.last_report)

    def execute_recommendations(self):
        """Execute approved recommendations"""
        # Load recommendations
        try:
            data = load_json(self.recommendations_file)
            if not data or 'recommended_actions' not in data:
                console.print("[yellow]No recommendations to execute. Run analysis first.[/yellow]")
                return
        except Exception as e:
            console.print(f"[red]Error loading recommendations: {e}[/red]")
            return

        actions = data['recommended_actions']
        if not actions:
            console.print("[yellow]No actions to execute.[/yellow]")
            return

        # Display actions
        console.print("\n[bold]Recommended Actions:[/bold]\n")
        for i, action in enumerate(actions, 1):
            console.print(f"{i}. {action['action'].upper()} {action['symbol']} - {action['quantity']} shares")

        # Confirm
        if not Confirm.ask("\n[bold yellow]Execute these trades?[/bold yellow]", default=False):
            console.print("[dim]Cancelled.[/dim]")
            return

        # Check if market is open
        if not self.alpaca.is_market_open():
            console.print("\n[yellow]⚠️  Market is currently closed. Orders will be queued for next market open.[/yellow]")
            if not Confirm.ask("Continue?", default=False):
                return

        # Execute trades
        console.print("\n[bold]Executing trades...[/bold]\n")
        for action in actions:
            try:
                symbol = action['symbol']
                quantity = action['quantity']
                side = action['action']  # 'buy' or 'sell'

                console.print(f"[dim]Placing {side} order for {quantity} shares of {symbol}...[/dim]")

                order = self.alpaca.place_order(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    order_type='market'
                )

                if order:
                    console.print(f"[green]✓ Order placed: {side} {quantity} {symbol}[/green]")
                else:
                    console.print(f"[red]✗ Failed to place order for {symbol}[/red]")

            except Exception as e:
                console.print(f"[red]Error executing {action['symbol']}: {e}[/red]")

        console.print("\n[green]✅ Trade execution complete![/green]")
        console.print("[dim]Refreshing portfolio...[/dim]")
        self.refresh_portfolio()

    def view_market_status(self):
        """Display market status"""
        try:
            is_open = self.alpaca.is_market_open()
            status = "[green]OPEN[/green]" if is_open else "[red]CLOSED[/red]"
            console.print(f"\n[bold]Market Status:[/bold] {status}")

            if not is_open:
                console.print("[dim]Note: Orders placed while market is closed will execute at next market open.[/dim]")
        except Exception as e:
            console.print(f"[red]Error checking market status: {e}[/red]")


def main():
    """Entry point"""
    try:
        cli = PortfolioManagerCLI()
        cli.run()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted. Goodbye! 👋[/yellow]\n")
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]\n")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


if __name__ == '__main__':
    main()
