# -*- coding: utf-8 -*-
"""LSTM_Retail.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1LrujJ1zlh_kcnmUcm-sR7OvvahvAKU0P

# Importing libraries

Importing  tensorflow and basic data science libraries.
"""

# Commented out IPython magic to ensure Python compatibility.
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
# %matplotlib inline

from sklearn.preprocessing  import MinMaxScaler
from tensorflow.keras.preprocessing.sequence import TimeseriesGenerator

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, LSTM, Dropout
from tensorflow.keras.callbacks import EarlyStopping

from sklearn.metrics import mean_squared_error

"""# Scraping and preprocessing data

Scraping data from IBGE, organizing columns and rows, converting dates into datetime (since they were originally hardcoded in portuguese).
"""

# Import csv from IBGE website
df = pd.read_csv('https://sidra.ibge.gov.br/geratabela?format=us.csv&name=tabela3416.csv&terr=N&rank=-&query=t/3416/n1/all/v/564/p/all/c11046/40311/d/v564%201/l/v,c11046,t%2Bp',
                 skiprows=3, index_col=1)

# Drops unwanted column
df = df.drop(['Unnamed: 0'], axis=1) 

# Drops metadata at the end of the dataframe
df = df[:-10] 

# Converts dates into datetime (they were originally in hardcoded Portuguese)
df['date'] = df.index
new = df["date"].str.split(" ", n = 1, expand = True) 
df["Month"]= new[0] 
df["Year"]= new[1] 
df.drop(columns =["date"], inplace = True) 
daysofweek = {
    'janeiro':'01',
    'fevereiro': '02',
    'março': '03',
    'abril': '04',
    'maio': '05',
    'junho': '06',
    'julho': '07',
    'agosto': '08',
    'setembro': '09',
    'outubro': '10',
    'novembro': '11',
    'dezembro': '12'
}
for key, value in daysofweek.items():
  df = df.replace(key,value)
df['Date'] = df['Month'] + '/'+ df['Year']
df['Date'] = pd.to_datetime(df['Date'])
df.index = df['Date']
df = df.drop(['Month', 'Year', 'Date'], axis=1)

# Renaming column
df.columns = ['Retail Sales Index - Brazil - 2014=100']

# Plotting Time Series
plt.style.use('seaborn-whitegrid')
df.plot(figsize=(10,6))

"""# Splitting and creating a gridsearch pipeline"""

# Creating a 24 months test size 
test_size = 24

# Length of Batches, 12 months = 1 year to capture seasonality
length = 12
test_ind = len(df) - test_size

# Spliting the data
train = df.iloc[:test_ind]
test = df.iloc[test_ind:]

# Scaling the Data
scaler = MinMaxScaler()
scaled_train = scaler.fit_transform(train)
scaled_test = scaler.transform(test)

# Time series generator, creating batches
generator = TimeseriesGenerator(scaled_train, scaled_train,
                                length=length, batch_size=1)

n_features = 1 # Just one feature, Sales Index

# Creating method for model gridsearch

def train_test(h_units, h_dropout, h_optimizer):
  model = Sequential()
  model.add(LSTM(h_units, activation='relu',input_shape=(length,n_features), return_sequences=True))
  model.add(Dropout(h_dropout))
  model.add(LSTM(64, activation='relu',input_shape=(length,n_features)))
  model.add(Dropout(h_dropout))
  model.add(Dense(1))
  model.compile(optimizer=h_optimizer,loss='mse')

  # Creates an early stop mechanism
  early_stop = EarlyStopping(monitor='val_loss',patience=3)
  validation_generator = TimeseriesGenerator(scaled_test, scaled_test,
                                            length=length, batch_size=1)
  # Fitting the model
  model.fit(generator,epochs=200,
            validation_data=validation_generator,
            callbacks=[early_stop], verbose =0)
  
  test_predictions = []

  # Storing losses
  losses = pd.DataFrame(model.history.history)

  # Updating current_batch with predictions, so the model predicts based on previous predicted values
  first_eval_batch = scaled_train[-length:]
  current_batch = first_eval_batch.reshape((1,length,n_features))

  for i in range(len(test)):
      current_pred = model.predict(current_batch)[0]
      test_predictions.append(current_pred)
      current_batch = np.append(current_batch[:,1:,:],[[current_pred]], axis=1)

  # Inverse transforming predictions and adding them to a df with the test set
  true_predictions = scaler.inverse_transform(test_predictions)
  real_vs_pred = test
  real_vs_pred['Predictions'] = true_predictions
  rmse = np.sqrt(mean_squared_error(real_vs_pred.iloc[:,0], real_vs_pred.iloc[:,1]))
  
  # Returns prediction RMSE (Root Mean Square Error)
  return rmse, losses, real_vs_pred

# GRIDSEARCH
# Hyperparameters List
unitlist = [128, 172, 256]
droplist = [0.1, 0.2, 0.3]
optimizerlist = ['adam', 'rmsprop']

# Initialising grid dictionaries
grid_rmse = {}
grid_losses = {}
grid_real_pred = {}

# Running the models
for unit in unitlist:
  for drop in droplist:
    for optim in optimizerlist:
      # Fetching results from the model
      model_rmse, losses_df, real_vs_pred = train_test(unit, drop, optim)
      
      # Adding results to the dictionaries
      current_model = '{} units, {} dropout, {} optimizer, {} epochs'.format(unit,drop,optim, len(losses_df))
      grid_rmse[current_model] = model_rmse
      grid_losses[current_model] = losses_df
      grid_real_pred[current_model] = real_vs_pred

      nr_of_models = str(len(unitlist)*len(droplist)*len(optimizerlist))
      print(str(len(grid_rmse.items())) + " out of " + nr_of_models)

# Selecting best model based on RMSE
grid_rmse_df = pd.DataFrame.from_dict(grid_rmse.items())
best_model = grid_rmse_df.sort_values(by=1)[0].iloc[0]
print(best_model)

grid_losses[best_model].plot(title='Loss and validation loss throughout epochs')

grid_real_pred[best_model].plot(figsize = (10,6), title='Real vs Predicted')
plt.grid(None)

grid_real_pred[best_model]

"""# FORECASTING

Forecasting into the unknown future (12 months)
"""

# Scaling the whole df
full_scaler = MinMaxScaler()
scaled_full_data = full_scaler.fit_transform(df)
length = 12

# Generator
generator = TimeseriesGenerator(scaled_full_data, scaled_full_data,
                                length=length, batch_size=1)
# Best model:
# 256 units, 0.3 dropout, adam optimizer, 17 epochs
                          
model = Sequential()
model.add(LSTM(256, activation='relu',input_shape=(length,n_features), return_sequences=True))
model.add(Dropout(0.3))
model.add(LSTM(64, activation='relu',input_shape=(length,n_features)))
model.add(Dropout(0.3))
model.add(Dense(1))
model.compile(optimizer='adam',loss='mse')

model.fit(generator, epochs=17)

# Forecasting the unknown future
forecast = []
periods = 14
first_eval_batch = scaled_full_data[-length:]
current_batch = first_eval_batch.reshape((1,length,n_features))

# Updating batches with predicted values
for i in range(periods):
    current_pred = model.predict(current_batch)[0]
    forecast.append(current_pred)
    current_batch = np.append(current_batch[:,1:,:],[[current_pred]], axis=1)

# Inverse transforming and indexing
forecast = scaler.inverse_transform(forecast)
forecast_index = pd.date_range(start='2020-03-01', periods=periods,
                               freq='MS')

# Merging forecast and index
forecast_df = pd.DataFrame(data=forecast, index=forecast_index,
                           columns=['Forecast'])

# Plotting forecast
ax = df.plot(figsize=(10, 6))
forecast_df.plot(ax=ax, figsize=(10, 6), title=('14 months Forecast'))
plt.xlim('2010-01-01','2021-05-01')
plt.tight_layout()