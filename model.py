import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model
import joblib
import os


class PricePredictor:
    def __init__(self, model_dir='model_artifacts'):
        self.model_dir = model_dir
        self.model = None
        self.scaler = None
        self.encoder = None
        self.product_categories = None
        self.features = ['farmprice', 'product_code', 'year', 'month', 'day', 'day_of_week']
        
    def load(self):
        """Load all artifacts"""
        try:
            model_path = os.path.join(self.model_dir, 'price_model.h5')
            if os.path.isdir(model_path):  
                self.model = tf.keras.models.load_model(model_path)
            else: 
                self.model = load_model(model_path)
            
            self.scaler = joblib.load(os.path.join(self.model_dir, 'scaler.pkl'))
            self.encoder = joblib.load(os.path.join(self.model_dir, 'encoder.pkl'))
            self.product_categories = joblib.load(os.path.join(self.model_dir, 'product_categories.pkl'))

            product_encoding = joblib.load('model_artifacts/product_encoding.pkl')

            index_to_product = {idx: product for product, idx in product_encoding.items()}
            print("Соответствие индексов и названий продуктов:")
            for idx, product in sorted(index_to_product.items()):
                print(f"Индекс {idx}: {product}")
            
            return True
        except Exception as e:
            print(f"Error loading artifacts: {str(e)}")
            return False
    
    def predict(self, input_data):
        """Make prediction from input dictionary"""
        if None in [self.model, self.scaler, self.encoder]:
            raise RuntimeError("Please load artifacts first with load()")
            
        try:
            input_df = pd.DataFrame([input_data])
            
            missing = set(self.features) - set(input_df.columns)
            if missing:
                raise ValueError(f"Missing features: {missing}")
                
            if input_df['product_code'].iloc[0] not in self.product_categories:
                print(f"Warning: Unknown product code {input_df['product_code'].iloc[0]}")
            
            scaled = self.scaler.transform(input_df[self.features[:-1]])
            encoded = self.encoder.transform(input_df[['product_code']]).toarray()
            final_input = np.concatenate([scaled, encoded], axis=1)
            
            return float(self.model.predict(final_input)[0][0])
            
        except Exception as e:
            print(f"Prediction failed: {str(e)}")
            raise