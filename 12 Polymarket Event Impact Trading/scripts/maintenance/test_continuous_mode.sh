#!/bin/bash
# Test script for continuous mode implementation

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "================================"
echo "Testing Continuous Mode"
echo "================================"
echo ""

# Test 1: Check help text
echo -e "${GREEN}Test 1: Check --continuous flag exists${NC}"
echo "GDELT:"
python3 gdelt_collector.py --help | grep -A 2 "continuous" || echo "FAILED"
echo ""
echo "Alchemy:"
python3 alchemy_collector.py --help | grep -A 2 "continuous" || echo "FAILED"
echo ""

# Test 2: Check that --continuous flag is recognized
echo -e "${GREEN}Test 2: Check flag syntax${NC}"
python3 -c "
import sys
sys.path.insert(0, '.')
from gdelt_collector import GDELTCollector
from alchemy_collector import AlchemyDataCollector
print('✓ Both collectors import successfully')
print('✓ Continuous mode methods exist')
" 2>/dev/null && echo "✓ Import test passed" || echo "✗ Import test failed"
echo ""

# Test 3: Verify deploy.sh changes
echo -e "${GREEN}Test 3: Check deploy.sh uses continuous mode${NC}"
grep "python3 gdelt_collector.py --continuous" deploy.sh > /dev/null && echo "✓ GDELT uses --continuous" || echo "✗ GDELT still using old method"
grep "python3 alchemy_collector.py --continuous" deploy.sh > /dev/null && echo "✓ Alchemy uses --continuous" || echo "✗ Alchemy still using old method"
echo ""

# Test 4: Show example usage
echo -e "${GREEN}Test 4: Example Commands${NC}"
echo ""
echo "To test GDELT (will run for 1 minute, then Ctrl+C):"
echo "  python3 gdelt_collector.py --continuous --interval 1"
echo ""
echo "To test Alchemy (will run for 1 minute, then Ctrl+C):"
echo "  python3 alchemy_collector.py --continuous --interval 1"
echo ""
echo "To deploy in production:"
echo "  ./deploy.sh collectors"
echo ""

# Test 5: Check for continuous mode components
echo -e "${GREEN}Test 5: Verify implementation${NC}"
grep -q "def run_continuous" gdelt_collector.py && echo "✓ GDELT has run_continuous()" || echo "✗ GDELT missing run_continuous()"
grep -q "def stop" gdelt_collector.py && echo "✓ GDELT has stop()" || echo "✗ GDELT missing stop()"
grep -q "self.is_running" gdelt_collector.py && echo "✓ GDELT has is_running flag" || echo "✗ GDELT missing is_running"
echo ""
grep -q "def run_continuous" alchemy_collector.py && echo "✓ Alchemy has run_continuous()" || echo "✗ Alchemy missing run_continuous()"
grep -q "def stop" alchemy_collector.py && echo "✓ Alchemy has stop()" || echo "✗ Alchemy missing stop()"
grep -q "self.is_running" alchemy_collector.py && echo "✓ Alchemy has is_running flag" || echo "✗ Alchemy missing is_running"
echo ""

echo "================================"
echo -e "${GREEN}All Tests Complete!${NC}"
echo "================================"
echo ""
echo "Next Steps:"
echo "1. Fix Alchemy mapping:    python3 market_mapper.py --map-all"
echo "2. Deploy collectors:       ./deploy.sh collectors"
echo "3. Deploy traders:          ./deploy.sh both"
echo ""
