# Polymarket Smart Money Detection Project Structure

## 📁 Project Overview
Bachelor 3 AI & Big Data Final Project - Smart Money Detection on Polymarket using warproxxx/poly_data pipeline

## 🗂️ Directory Structure

```
polymarket-smart-money-detection/
├── 📄 README.md                          # Project overview and setup
├── 📄 requirements.txt                    # Python dependencies
├── 📄 setup.py                           # Package setup
├── 📄 docker-compose.yml                  # Docker orchestration
├── 📄 config/                            # Configuration files
│   ├── ├── config.yaml                    # Main configuration
│   ├── ├── api_keys.yaml                 # API credentials
│   └── ├── model_config.yaml              # ML model parameters
├── 📄 data/                              # Data storage and processing
│   ├── ├── raw/                          # Raw data from warproxxx/poly_data
│   ├── ├── processed/                    # Cleaned and transformed data
│   ├── ├── features/                     # Engineered features
│   ├── ├── models/                       # Trained ML models
│   └── ├── exports/                      # Export results and visualizations
├── 📄 src/                               # Source code
│   ├── ├── data_collection/              # Data ingestion pipeline
│   │   ├── ├── poly_data_integration.py  # warproxxx/poly_data wrapper
│   │   ├── ├── hyper_sync_client.py      # HyperSync connection
│   │   ├── ├── clob_api_client.py         # CLOB API client
│   │   └── ├── data_validator.py        # Data validation and cleaning
│   ├── ├── feature_engineering/          # Feature extraction and engineering
│   │   ├── ├── wallet_features.py         # Wallet behavior features
│   │   ├── ├── market_features.py         # Market-level features
│   │   ├── ├── network_features.py       # Network analysis features
│   │   └── ├── time_series_features.py   # Temporal features
│   ├── ├── ml_models/                    # Machine learning models
│   │   ├── ├── clustering/               # Wallet clustering algorithms
│   │   │   ├── ├── kmeans_clustering.py  # K-Means implementation
│   │   │   ├── ├── dbscan_clustering.py  # DBSCAN implementation
│   │   │   └── ├── ├── cluster_evaluator.py # Cluster evaluation
│   │   ├── ├── classification/           # Smart Money classification
│   │   │   ├── ├── random_forest.py      # Random Forest classifier
│   │   │   ├── ├── xgboost_classifier.py # XGBoost classifier
│   │   │   └── ├── ├── model_evaluator.py # Model evaluation
│   │   ├── ├── anomaly_detection/        # Anomaly detection models
│   │   │   ├── ├── lstm_anomaly.py       # LSTM-based anomaly detection
│   │   │   ├── ├── arima_anomaly.py      # ARIMA-based anomaly detection
│   │   │   └── ├── ├── isolation_forest.py # Isolation Forest
│   │   └── ├── network_analysis/         # Social network analysis
│   │       ├── ├── graph_construction.py # Network graph building
│   │       ├── ├── community_detection.py # Community detection
│   │       └── ├── ├── centrality_metrics.py # Network centrality
│   ├── ├── analysis/                      # Analysis and reporting
│   │   ├── ├── statistical_analysis.py   # Statistical analysis
│   │   ├── ├── hypothesis_testing.py     # Hypothesis testing
│   │   ├── ├── backtesting.py            # Strategy backtesting
│   │   └── ├── ├── report_generator.py   # Report generation
│   ├── ├── visualization/                # Data visualization
│   │   ├── ├── dashboard/                # Streamlit dashboard
│   │   │   ├── ├── app.py                # Main dashboard application
│   │   │   ├── ├── pages/                # Dashboard pages
│   │   │   │   ├── ├── overview.py       # Overview page
│   │   │   │   ├── ├── smart_money.py    # Smart Money analysis
│   │   │   │   ├── ├── network_view.py   # Network visualization
│   │   │   │   ├── ├── alerts.py         # Alert system
│   │   │   │   └── ├── settings.py       # Settings page
│   │   │   ├── ├── components/           # Dashboard components
│   │   │   │   ├── ├── charts.py         # Chart components
│   │   │   │   ├── ├── tables.py         # Table components
│   │   │   │   ├── ├── filters.py        # Filter components
│   │   │   │   └── ├── ├── utils.py      # Utility functions
│   │   ├── ├── plots/                    # Static plots and charts
│   │   │   ├── ├── wallet_analysis.py     # Wallet behavior plots
│   │   │   ├── ├── network_plots.py       # Network visualization
│   │   │   ├── ├── time_series_plots.py  # Time series analysis
│   │   │   └── ├── ├── distribution_plots.py # Statistical distributions
│   │   └── ├── interactive/              # Interactive visualizations
│   │       ├── ├── plotly_charts.py      # Plotly interactive charts
│   │       └── ├── ├── network_viz.py    # Interactive network visualization
│   ├── ├── utils/                        # Utility functions
│   │   ├── ├── database.py               # Database utilities (DuckDB)
│   │   ├── ├── data_processing.py        # Data processing utilities
│   │   ├── ├── ml_utils.py               # Machine learning utilities
│   │   ├── ├── api_utils.py              # API utilities
│   │   ├── ├── logger.py                 # Logging configuration
│   │   └── ├── ├── config_loader.py      # Configuration management
│   └── ├── tests/                        # Unit tests
│       ├── ├── data_collection_tests/   # Data collection tests
│       ├── ├── feature_engineering_tests/ # Feature engineering tests
│       ├── ├── ml_model_tests/           # ML model tests
│       ├── ├── analysis_tests/           # Analysis tests
│       └── ├── integration_tests/        # Integration tests
├── 📄 notebooks/                         # Jupyter notebooks for analysis
│   ├── ├── 01_data_collection.ipynb     # Data collection and exploration
│   ├── ├── 02_feature_engineering.ipynb  # Feature engineering exploration
│   ├── ├── 03_ml_modeling.ipynb         # ML model development
│   ├── ├── 04_analysis.ipynb             # Statistical analysis
│   ├── ├── 05_backtesting.ipynb          # Strategy backtesting
│   └── ├── ├── 06_dashboard_demo.ipynb   # Dashboard demonstration
├── 📄 docs/                             # Documentation
│   ├── ├── README.md                     # Documentation overview
│   ├── ├── api/                          # API documentation
│   │   ├── ├── data_collection_api.md    # Data collection API
│   │   ├── ├── ml_models_api.md          # ML models API
│   │   └── ├── ├── dashboard_api.md     # Dashboard API
│   ├── ├── methodology/                  # Methodology documentation
│   │   ├── ├── data_pipeline.md          # Data pipeline documentation
│   │   ├── ├── ml_algorithms.md          # ML algorithms documentation
│   │   └── ├── ├── analysis_framework.md # Analysis framework
│   ├── ├── setup/                       # Setup and installation
│   │   ├── ├── installation.md           # Installation guide
│   │   ├── ├── configuration.md          # Configuration guide
│   │   └── ├── ├── deployment.md         # Deployment guide
│   └── ├── examples/                    # Usage examples
│       ├── ├── basic_usage.py            # Basic usage example
│       ├── ├── advanced_analysis.py      # Advanced analysis example
│       └── ├── ├── custom_models.py      # Custom model example
├── 📄 scripts/                          # Utility scripts
│   ├── ├── data_ingestion.py            # Data ingestion script
│   ├── ├── model_training.py             # Model training script
│   ├── ├── analysis_runner.py            # Analysis runner script
│   ├── ├── dashboard_runner.py           # Dashboard runner script
│   ├── ├── export_results.py             # Results export script
│   └── ├── ├── backup_data.py            # Data backup script
├── 📄 results/                          # Results and outputs
│   ├── ├── models/                      # Trained model files
│   ├── ├── reports/                     # Analysis reports
│   ├── ├── visualizations/               # Generated visualizations
│   ├── ├── exports/                     # Exported data
│   └── ├── logs/                        # Application logs
├── 📄 .gitignore                        # Git ignore file
├── 📄 LICENSE                           # Project license
└── 📄 .env                              # Environment variables
```

## 🏗️ Key Components

### 1. **Data Collection Layer**
- **poly_data_integration.py**: Wrapper for warproxxx/poly_data pipeline
- **hyper_sync_client.py**: Real-time blockchain data streaming
- **clob_api_client.py**: Market data and order book access
- **data_validator.py**: Data quality validation and cleaning

### 2. **Feature Engineering Layer**
- **wallet_features.py**: PnL, Win Rate, Maker/Taker ratio calculations
- **market_features.py**: Market-level features and indicators
- **network_features.py**: Social network analysis features
- **time_series_features.py**: Temporal and sequential features

### 3. **Machine Learning Layer**
- **clustering/**: Wallet behavior clustering (K-Means, DBSCAN)
- **classification/**: Smart Money classification models
- **anomaly_detection/**: Anomaly detection in trading patterns
- **network_analysis/**: Social network and community detection

### 4. **Analysis Layer**
- **statistical_analysis.py**: Statistical testing and analysis
- **hypothesis_testing.py**: Scientific hypothesis validation
- **backtesting.py**: Strategy performance validation
- **report_generator.py**: Automated report generation

### 5. **Visualization Layer**
- **dashboard/**: Real-time Streamlit dashboard
- **plots/**: Static and interactive visualizations
- **interactive/**: Plotly-based interactive charts

### 6. **Infrastructure Layer**
- **Docker**: Containerized deployment
- **DuckDB**: High-performance analytical database
- **Streamlit**: Real-time dashboard framework
- **Cloud**: Scalable cloud infrastructure

## 🔧 Key Technologies

- **Data Processing**: Python, Pandas, Polars, DuckDB
- **Machine Learning**: Scikit-learn, PyTorch, XGBoost, NetworkX
- **Data Collection**: warproxxx/poly_data, HyperSync, CLOB API
- **Visualization**: Streamlit, Plotly, Matplotlib, Seaborn
- **Infrastructure**: Docker, Kubernetes, Cloud (AWS/GCP)
- **Database**: DuckDB, PostgreSQL
- **API**: FastAPI, AsyncIO

## 📊 Data Flow

```
warproxxx/poly_data → HyperSync/CLOB API → Data Validation → Feature Engineering → 
ML Models → Analysis → Dashboard → Results Export
```

## 🚀 Quick Start

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd polymarket-smart-money-detection
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. **Run data collection**:
   ```bash
   python scripts/data_ingestion.py
   ```

4. **Train models**:
   ```bash
   python scripts/model_training.py
   ```

5. **Start dashboard**:
   ```bash
   python scripts/dashboard_runner.py
   ```

## 📈 Expected Outputs

- **Smart Wallet Classification**: Identified Smart Money wallets with confidence scores
- **Network Analysis**: Detected coordinated trading patterns and communities
- **Anomaly Detection**: Real-time alerts for unusual trading behavior
- **Performance Metrics**: Model accuracy, precision, recall, and business metrics
- **Interactive Dashboard**: Real-time monitoring and analysis interface
- **Research Reports**: Academic-quality analysis and validation results