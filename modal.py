class PricePredictor:
    def __init__(self, model_dir='.'):
        self.model_dir = model_dir
        self.model = None
        self.scaler = None
        self.encoder = None
        self.product_categories = None
        self.features = ['farmprice', 'product_code', 'year', 'month', 'day', 'day_of_week']
        
    def load(self):
        """Load all artifacts"""
        try:
            # Load model (supports both .h5 and saved_model formats)
            model_path = os.path.join(self.model_dir, 'price_model.h5')
            if os.path.isdir(model_path):  # For saved_model format
                self.model = tf.keras.models.load_model(model_path)
            else:  # For .h5 format
                self.model = load_model(model_path)
            
            # Load preprocessing objects
            self.scaler = joblib.load(os.path.join(self.model_dir, 'scaler.pkl'))
            self.encoder = joblib.load(os.path.join(self.model_dir, 'encoder.pkl'))
            self.product_categories = joblib.load(os.path.join(self.model_dir, 'product_categories.pkl'))
            
            return True
        except Exception as e:
            print(f"Error loading artifacts: {str(e)}")
            return False
    
    def predict(self, input_data):
        """Make prediction from input dictionary"""
        if None in [self.model, self.scaler, self.encoder]:
            raise RuntimeError("Please load artifacts first with load()")
            
        try:
            # Convert to DataFrame
            input_df = pd.DataFrame([input_data])
            
            # Validate features
            missing = set(self.features) - set(input_df.columns)
            if missing:
                raise ValueError(f"Missing features: {missing}")
                
            # Validate product code
            if input_df['product_code'].iloc[0] not in self.product_categories:
                print(f"Warning: Unknown product code {input_df['product_code'].iloc[0]}")
            
            # Preprocess
            scaled = self.scaler.transform(input_df[self.features[:-1]])
            encoded = self.encoder.transform(input_df[['product_code']]).toarray()
            final_input = np.concatenate([scaled, encoded], axis=1)
            
            # Predict
            return float(self.model.predict(final_input)[0][0])
            
        except Exception as e:
            print(f"Prediction failed: {str(e)}")
            raise