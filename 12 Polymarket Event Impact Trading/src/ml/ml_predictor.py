#!/usr/bin/env python3
"""
ML Predictor Module
Provides ML prediction capabilities for all trading bots.
"""

import pickle
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class MLPredictor:
    """
    ML prediction engine for trading bots.
    Loads trained models and makes predictions with confidence scores.
    """
    
    def __init__(self, model_path: str, confidence_threshold: float = 0.60,
                 enabled: bool = True):
        """
        Initialize ML predictor.
        
        Args:
            model_path: Path to trained model .pkl file
            confidence_threshold: Minimum confidence to recommend trade (0-1)
            enabled: Whether ML predictions are enabled
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.enabled = enabled
        
        self.model = None
        self.feature_names = None
        self.model_info = None
        
        if self.enabled:
            self._load_model()
    
    def _load_model(self):
        """Load the trained model from disk."""
        try:
            model_file = Path(self.model_path)
            if not model_file.exists():
                logger.warning(f"ML model not found: {self.model_path}")
                logger.warning("ML predictions disabled. Using rule-based trading only.")
                self.enabled = False
                return
            
            logger.info(f"Loading ML model from {self.model_path}")
            with open(model_file, 'rb') as f:
                self.model_info = pickle.load(f)
            
            self.model = self.model_info['model']
            self.feature_names = self.model_info['feature_names']
            
            metrics = self.model_info.get('metrics', {})
            logger.info(f"✅ ML model loaded successfully")
            logger.info(f"   Training accuracy: {metrics.get('accuracy', 0)*100:.2f}%")
            logger.info(f"   ROC AUC: {metrics.get('roc_auc', 0)*100:.2f}%")
            logger.info(f"   Features: {len(self.feature_names)}")
            logger.info(f"   Confidence threshold: {self.confidence_threshold*100:.1f}%")
            
        except Exception as e:
            logger.error(f"Error loading ML model: {e}")
            logger.warning("ML predictions disabled. Using rule-based trading only.")
            self.enabled = False
    
    def extract_features(self, market: Dict, additional_context: Optional[Dict] = None) -> Dict:
        """
        Extract features from market data for ML prediction.
        
        Args:
            market: Market dictionary with price, question, etc.
            additional_context: Optional additional context (event info, etc.)
        
        Returns:
            Dictionary of features
        """
        # Get market price (handle different price field names)
        price = market.get('price', market.get('outcomePrices', [0.5])[0])
        if isinstance(price, list):
            price = price[0] if len(price) > 0 else 0.5
        price = float(price)
        price = max(0.001, min(0.999, price))  # Clip to valid range
        
        # Basic price features
        features = {
            'trade_price': price,
            'price_squared': price ** 2,
            'price_cubed': price ** 3,
            'log_price': np.log(price),
            'price_distance_from_half': abs(price - 0.5),
            'betting_yes': 1 if price > 0.5 else 0,
            'betting_no': 1 if price < 0.5 else 0,
            'market_confidence': abs(price - 0.5) * 2,
        }
        
        # Time features
        now = datetime.now()
        features['hour_of_day'] = now.hour
        features['day_of_week'] = now.weekday()
        features['is_weekend'] = 1 if now.weekday() >= 5 else 0
        
        # Market features
        question = market.get('question', '')
        features['question_length'] = len(question)
        features['question_words'] = len(question.split())
        
        # Market type detection
        question_lower = question.lower()
        features['is_sports'] = int(any(kw in question_lower for kw in [
            'win', 'championship', 'bowl', 'playoff', 'coach', 'mvp', 'athlete'
        ]))
        features['is_politics'] = int(any(kw in question_lower for kw in [
            'election', 'president', 'mayor', 'vote', 'poll'
        ]))
        features['is_crypto'] = int(any(kw in question_lower for kw in [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'blockchain',
            'fed', 'interest', 'rate'
        ]))
        
        return features
    
    def predict(self, market: Dict, additional_context: Optional[Dict] = None) -> Tuple[bool, float, str]:
        """
        Make a prediction for a market.
        
        Args:
            market: Market dictionary
            additional_context: Optional additional context
        
        Returns:
            Tuple of (should_trade, confidence, reason)
        """
        if not self.enabled or self.model is None:
            return False, 0.0, "ML disabled"
        
        try:
            # Extract features
            features = self.extract_features(market, additional_context)
            
            # Create DataFrame with correct feature order
            feature_values = [features.get(fname, 0) for fname in self.feature_names]
            X = pd.DataFrame([feature_values], columns=self.feature_names)
            
            # Get prediction
            prob_correct = self.model.predict_proba(X)[0][1]
            
            # Determine if we should trade
            should_trade = prob_correct >= self.confidence_threshold
            
            # Create reason string
            if should_trade:
                reason = f"ML: {prob_correct*100:.1f}% confidence (>={self.confidence_threshold*100:.0f}%)"
            else:
                reason = f"ML: {prob_correct*100:.1f}% confidence (<{self.confidence_threshold*100:.0f}%)"
            
            logger.debug(f"ML prediction for {market.get('question', 'Unknown')[:50]}: "
                        f"{prob_correct*100:.1f}% conf → {'TRADE' if should_trade else 'SKIP'}")
            
            return should_trade, prob_correct, reason
            
        except Exception as e:
            logger.error(f"Error making ML prediction: {e}")
            return False, 0.0, f"ML error: {str(e)}"
    
    def should_trade(self, market: Dict, additional_context: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Simplified interface: just returns whether to trade.
        
        Args:
            market: Market dictionary
            additional_context: Optional additional context
        
        Returns:
            Tuple of (should_trade, reason)
        """
        should_trade, confidence, reason = self.predict(market, additional_context)
        return should_trade, reason
    
    def get_confidence(self, market: Dict, additional_context: Optional[Dict] = None) -> float:
        """
        Get just the confidence score.
        
        Args:
            market: Market dictionary
            additional_context: Optional additional context
        
        Returns:
            Confidence score (0-1)
        """
        _, confidence, _ = self.predict(market, additional_context)
        return confidence
    
    def get_position_size_multiplier(self, confidence: float) -> float:
        """
        Calculate position size multiplier based on confidence.
        Uses Kelly criterion inspired approach.
        
        Args:
            confidence: Model confidence (0-1)
        
        Returns:
            Multiplier (0-1) to apply to base position size
        """
        if confidence < self.confidence_threshold:
            return 0.0
        
        # Scale from threshold to 1.0 → 0.5 to 1.0 multiplier
        # This means minimum confidence gets 50% of base size
        # Maximum confidence (1.0) gets 100% of base size
        range_min = self.confidence_threshold
        range_max = 1.0
        
        scaled = (confidence - range_min) / (range_max - range_min)
        multiplier = 0.5 + (scaled * 0.5)  # Maps to 0.5-1.0
        
        return min(1.0, max(0.0, multiplier))
    
    def get_stats(self) -> Dict:
        """Get model statistics."""
        if not self.enabled or self.model_info is None:
            return {'enabled': False}
        
        return {
            'enabled': True,
            'model_path': self.model_path,
            'confidence_threshold': self.confidence_threshold,
            'metrics': self.model_info.get('metrics', {}),
            'training_date': self.model_info.get('training_date', 'Unknown'),
            'feature_count': len(self.feature_names) if self.feature_names else 0
        }


class MLPredictorFactory:
    """Factory for creating ML predictors for different bots."""
    
    @staticmethod
    def create_for_bot(bot_name: str, config: Dict) -> MLPredictor:
        """
        Create ML predictor for a specific bot.
        
        Args:
            bot_name: Name of bot ('event', 'price_level', 'short_expiry')
            config: Bot configuration
        
        Returns:
            MLPredictor instance
        """
        # Get ML config
        ml_enabled = config.get('use_ml_model', False)
        ml_confidence = config.get('ml_confidence_threshold', 0.60)
        ml_model_path = config.get('ml_model_path')
        
        # Default model path if not specified
        if ml_model_path is None:
            ml_model_path = f'data/models/{bot_name}_model.pkl'
        
        logger.info(f"Initializing ML predictor for {bot_name}")
        logger.info(f"  Enabled: {ml_enabled}")
        logger.info(f"  Model path: {ml_model_path}")
        logger.info(f"  Confidence threshold: {ml_confidence*100:.1f}%")
        
        return MLPredictor(
            model_path=ml_model_path,
            confidence_threshold=ml_confidence,
            enabled=ml_enabled
        )
