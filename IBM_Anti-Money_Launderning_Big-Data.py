# -*- coding: utf-8 -*-
"""Big data IBM AML.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Kv4UBiZNOw6SUmJTeV8fWldV0HJ_bUmZ
"""

import os
import json
import zipfile
from pyspark.sql import SparkSession
import random
from pyspark.sql.types import StructType, StructField, StringType, FloatType, IntegerType, DoubleType
from pyspark.sql import functions as F
from pyspark.sql.functions import col, sum, when, count, avg, to_timestamp, hour, dayofweek
from pyspark.ml.feature import StringIndexer, VectorAssembler, StandardScaler
from pyspark.sql import Window
import seaborn as sns
import matplotlib.pyplot as plt
from pyspark.ml.stat import Correlation
import numpy as np
from pyspark.ml import Pipeline
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator

# Initialize Spark session
spark = SparkSession.builder \
    .appName("Anti-Money Laundering") \
    .getOrCreate()

# Define schema for the CSV file
schema = StructType([
    StructField("Timestamp", StringType(), True),
    StructField("From_Bank", StringType(), True),
    StructField("From_Account", StringType(), True),
    StructField("To_Bank", StringType(), True),
    StructField("To_Account", StringType(), True),
    StructField("Amount_Received", FloatType(), True),
    StructField("Receiving_Currency", StringType(), True),
    StructField("Amount_Paid", FloatType(), True),
    StructField("Payment_Currency", StringType(), True),
    StructField("Payment_Format", StringType(), True)
])

# Load the CSV file
li_medium_df = spark.read.csv("/content/drive/MyDrive/Big data Final Project/LI-Medium_Trans.csv", schema=schema, header=True)

# Display the first few rows
li_medium_df.show(10)

# Load the TXT file
li_patterns_df = spark.read.text("/content/drive/MyDrive/Big data Final Project/LI-Medium_Patterns.txt.txt")

# Display the first few rows
li_patterns_df.show(10, truncate=False)

"""Identify Laundering Patterns"""

# Step 1: Extract "Pattern_Type" from BEGIN LAUNDERING ATTEMPT
patterns_df = li_patterns_df.withColumn(
    "Pattern_Type",
    F.when(F.col("value").rlike("BEGIN LAUNDERING ATTEMPT - (.+)"),
           F.regexp_extract(F.col("value"), "BEGIN LAUNDERING ATTEMPT - (.+)", 1))
)

# Step 2: Forward-fill the "Pattern_Type" column
window_spec = Window.orderBy(F.monotonically_increasing_id())
patterns_df = patterns_df.withColumn(
    "Pattern_Type",
    F.last("Pattern_Type", True).over(window_spec)
)

# Step 3: Filter out rows with "END LAUNDERING ATTEMPT"
patterns_df = patterns_df.filter(~F.col("value").contains("END LAUNDERING ATTEMPT"))

# Step 4: Filter for transaction rows
laundering_transactions = patterns_df.filter(patterns_df.value.rlike(r'\d{4}/\d{2}/\d{2}'))

# Split columns into structured fields
laundering_transactions = laundering_transactions.withColumn("Timestamp", F.split(F.col("value"), ",").getItem(0)) \
    .withColumn("From_Bank", F.split(F.col("value"), ",").getItem(1)) \
    .withColumn("From_Account", F.split(F.col("value"), ",").getItem(2)) \
    .withColumn("To_Bank", F.split(F.col("value"), ",").getItem(3)) \
    .withColumn("To_Account", F.split(F.col("value"), ",").getItem(4)) \
    .withColumn("Amount_Received", F.split(F.col("value"), ",").getItem(5)) \
    .withColumn("Receiving_currency", F.split(F.col("value"), ",").getItem(6)) \
    .withColumn("Amount_paid", F.split(F.col("value"), ",").getItem(7)) \
    .withColumn("Payment_currency", F.split(F.col("value"), ",").getItem(8)) \
    .withColumn("Payment_Format", F.split(F.col("value"), ",").getItem(9)) \
    .withColumn("isLaundering", F.split(F.col("value"), ",").getItem(10))

# Select required columns
laundering_transactions = laundering_transactions.select("Timestamp", "From_Bank", "Pattern_Type", "isLaundering")

# Display the results
laundering_transactions.show(5)

laundering_transactions.cache().groupBy("isLaundering").count().show()

"""Join and Label Transactions"""

# Join the transactions with laundering patterns
joined_df = li_medium_df.join(
    laundering_transactions,
    on=["Timestamp", "From_Bank"],
    how="left"
)

# Fill null values in "isLaundering" with 0
joined_df = joined_df.withColumn(
    "isLaundering",
    F.when(F.col("isLaundering").isNull(), 0).otherwise(F.col("isLaundering"))
)

# Convert "isLaundering" to integer
joined_df = joined_df.withColumn("isLaundering", F.col("isLaundering").cast("integer"))

# Display the labeled dataset
joined_df.show(10)

# Verify the schema change
joined_df.printSchema()

#size_in_memory_gb = joined_df.rdd.map(lambda row: len(str(row))).sum() / (1024 * 1024 * 1024)
#print(f"Approximate size in memory: ({size_in_memory_gb:.2f} GB)")

"""Check Data Balance"""

# Group by "isLaundering" and count
joined_df.groupBy("isLaundering").count().show()

"""Balance the data


DROP 50% of majority


Use SMOTE to generate synthetic data of minority after data engineering
"""

# Register joined_df as a temporary view to use SQL
joined_df.createOrReplaceTempView("joined_table")

# Calculate dynamic fraction for desired ratio
minority_count = joined_df.filter("isLaundering = 1").count()
majority_count = joined_df.filter("isLaundering = 0").count()
desired_ratio = 1.5  # Target ratio (majority:minority)

fraction = (desired_ratio * minority_count) / majority_count

# Modify SQL query with the calculated fraction
query = f"""
SELECT *
FROM joined_table
WHERE NOT ((Pattern_Type IS NULL) AND (isLaundering = 0) AND (rand() < {fraction}))
"""
balanced_df = spark.sql(query)



joined_df.unpersist()

balanced_df.cache().groupBy("isLaundering").count().show()

"""Data Cleaning and Exploration"""

# Count NULL values in each column
null_counts = balanced_df.select([sum(col(c).isNull().cast("int")).alias(c) for c in balanced_df.columns])

# Show the result
null_counts.show()

#Fill Missing Values
balanced_df = balanced_df.na.fill({
    "Pattern_Type": "Unknown"
})

"""Extract features such as Hour and DayOfWeek."""

balanced_df = balanced_df.withColumn("Timestamp", to_timestamp("Timestamp", "yyyy/MM/dd HH:mm")) \
                         .withColumn("Hour", hour("Timestamp")) \
                         .withColumn("DayOfWeek", dayofweek("Timestamp"))

balanced_df.show()

"""### Feature Engineering
Aggregated Features by Account using Window Functions:
Calculate FanOut, FanIn, and AvgAmountSent.

-FanOut:
how many different transactions it initiates.

-FanIn:
how many different transactions it receives.

-AvgAmountSent:
the typical transaction size for each account as a sender.
"""

# Window specifications
sender_window = Window.partitionBy("From_Account")
receiver_window = Window.partitionBy("To_Account")

# Calculate fan-out, fan-in, and average amount sent
featured_df = balanced_df.withColumn("FanOut", count("To_Account").over(sender_window)) \
                         .withColumn("FanIn", count("From_Account").over(receiver_window)) \
                         .withColumn("AvgAmountSent", avg("Amount_Paid").over(sender_window))

balanced_df.unpersist()
featured_df.cache().show()

"""Encode Categorical Variables:

Converted categorical columns into numerical indices using StringIndexer.
"""

currency_index = StringIndexer(inputCol="Receiving_Currency", outputCol="CurrencyIndex")
payment_format_index = StringIndexer(inputCol="Payment_Format", outputCol="PaymentFormatIndex")
pattern_type_index = StringIndexer(inputCol="Pattern_Type", outputCol="PatternTypeIndex")

featured_df = currency_index.fit(featured_df).transform(featured_df)
featured_df = payment_format_index.fit(featured_df).transform(featured_df)
featured_df = pattern_type_index.fit(featured_df).transform(featured_df)

featured_df.show()

select_col = ["Amount_Received", "FanOut", "FanIn", "AvgAmountSent",
                   "Hour", "DayOfWeek", "CurrencyIndex",
                   "PaymentFormatIndex", "PatternTypeIndex", "isLaundering"]
featured_df = featured_df.select(*select_col)

#size_in_memory_gb = featured_df.rdd.map(lambda row: len(str(row))).sum() / (1024 * 1024 * 1024)
#print(f"Approximate size in memory: ({size_in_memory_gb:.2f} GB)")

"""SMOTE to generate synthetic data for minority"""

# Step 1: Select only the required columns (excluding 'isLaundering')
feature_columns = ["Amount_Received", "FanOut", "FanIn", "AvgAmountSent",
                   "Hour", "DayOfWeek", "CurrencyIndex",
                   "PaymentFormatIndex", "PatternTypeIndex"]

# Select features for minority class (isLaundering = 1)
minority_df = featured_df.filter(F.col("isLaundering") == 1).select(*feature_columns)
majority_df = featured_df.filter(F.col("isLaundering") == 0).select(*feature_columns, "isLaundering")

featured_df.unpersist()

# Step 2: Define a function to generate synthetic samples (excluding isLaundering)
def generate_synthetic_samples(minority_data, num_samples=130):
    synthetic_samples = []

    for row in minority_data:
        base_vector = np.array([row[col] for col in feature_columns])

        # Find random neighbors within the minority class
        neighbors = random.sample(minority_data, k=num_samples)
        for neighbor in neighbors:
            neighbor_vector = np.array([neighbor[col] for col in feature_columns])

            # Interpolate to create a synthetic sample
            gap = np.random.rand()
            synthetic_vector = base_vector + gap * (neighbor_vector - base_vector)

            # Append the synthetic sample without the 'isLaundering' column
            synthetic_samples.append(tuple(synthetic_vector.tolist()))

    return synthetic_samples

# Step 3: Collect minority samples and generate synthetic samples
minority_data = minority_df.collect()
synthetic_samples = generate_synthetic_samples(minority_data, num_samples=130)

# Step 4: Define schema for synthetic samples without 'isLaundering'
schema = StructType([StructField(col, DoubleType(), True) for col in feature_columns])

# Create synthetic DataFrame from synthetic samples
synthetic_df = spark.createDataFrame(synthetic_samples, schema=schema)

# Step 5: Add 'isLaundering' column with value 1 to synthetic samples
synthetic_df = synthetic_df.withColumn("isLaundering", F.lit(1))

# Step 6: Combine the majority and synthetic DataFrames
balanced_featured_df = majority_df.union(synthetic_df)

# Display counts to confirm balancing
balanced_featured_df.cache().groupBy("isLaundering").count().show()

balanced_featured_df.show()

balanced_featured_df.groupBy("isLaundering").count().show()

"""Assemble Features into a Vector:

Use VectorAssembler to create a feature vector for model input.
"""

features_col = ["Amount_Received", "FanOut", "FanIn", "AvgAmountSent", "Hour", "DayOfWeek", "CurrencyIndex", "PaymentFormatIndex", "PatternTypeIndex"]
correlation_features = ["Amount_Received", "FanOut", "FanIn", "AvgAmountSent", "Hour", "DayOfWeek", "CurrencyIndex", "PaymentFormatIndex", "PatternTypeIndex", "isLaundering"]
assembler = VectorAssembler(inputCols=correlation_features, outputCol="corr_features")
df_vector = assembler.transform(balanced_featured_df)

"""Correlation Heatmap:

To assess relationships between features and identify strong predictors,
"""

# Calculate correlation matrix
correlation_matrix = Correlation.corr(df_vector, "corr_features").head()[0].toArray()

# Convert to a heatmap
plt.figure(figsize=(10, 8))
sns.heatmap(correlation_matrix, annot=True, xticklabels=correlation_features, yticklabels=correlation_features, cmap="coolwarm")
plt.title("Correlation Heatmap of Numerical Features")
plt.show()

"""Key Observations:
Moderate Correlations:

Amount_Received and AvgAmountSent have a moderately positive correlation (~0.43).
Implication: These features may capture overlapping information. Including both might introduce some redundancy but could still be beneficial if they represent distinct aspects of the data.
Strongest Predictor:

PatternTypeIndex has the strongest positive correlation with the target variable (isLaundering) at 0.68.
Implication: This is a highly predictive feature and must be included in the model.
Weak Positive Correlations:

CurrencyIndex (0.046) and PaymentFormatIndex (0.053) show weak positive correlations with isLaundering.
Implication: While weak individually, these features may still add value when combined with others.
Negative Correlations:

FanOut (-0.087) and DayOfWeek (-0.067) show weak negative correlations with isLaundering.
Implication: These features may still provide valuable signal, as they exhibit some relationship with the target variable.
Extremely Weak Correlations:

Amount_Received (0.0059) and FanIn (-0.01) show almost no correlation with isLaundering.
Implication: These features might not contribute significantly to the model and could potentially add noise.
Independent Features:

Most features (e.g., Hour, DayOfWeek, CurrencyIndex, etc.) have low correlations with each other.
Implication: This indicates minimal multicollinearity, so these features can independently contribute unique information to the model.
Key Takeaways:
Critical Features:

PatternTypeIndex is the most important feature and should definitely be included in the model.
Moderate correlation between Amount_Received and AvgAmountSent suggests the need to evaluate their combined effect on the model.
Potentially Useful Features:

Weakly correlated features like CurrencyIndex and PaymentFormatIndex may still enhance model performance, especially when used in combination.
Carefully Consider:

Features with extremely weak correlations (e.g., Amount_Received, FanIn) might add noise. Consider their inclusion carefully based on domain knowledge or during feature selection through model evaluation.
Feature Engineering:

Consider creating interaction features or transformations if certain weakly correlated features have nonlinear relationships with the target variable.
Next Steps:

Perform feature selection using techniques like recursive feature elimination (RFE) or permutation importance to validate the usefulness of these features.
Regularize the model (e.g., using L1/L2 regularization) to penalize any noise introduced by weak features.

Feature Selection
"""

# Define all features for the final assembler, using scaled and unscaled features
all_features = [ "FanOut", "AvgAmountSent", "DayOfWeek", "CurrencyIndex", "PaymentFormatIndex", "PatternTypeIndex"]

# Assemble the final feature vector for prediction
assembler_final = VectorAssembler(inputCols=all_features, outputCol="features")
balanced_featured_df = balanced_featured_df.select(all_features + ["isLaundering"])

"""Split the Data:

Split the data into training, validation, and test sets.
"""

train_df, val_df, test_df = balanced_featured_df.randomSplit([0.6, 0.2, 0.2], seed=42)
balanced_featured_df.unpersist()
train_df.cache()
val_df.cache()
test_df.cache()

"""Model Training with Pipeline

Created a Pipeline with Random Forest Classifier ML model:

Defined a pipeline to streamline the feature transformations and model training process
"""

# Update maxBins in the RandomForestClassifier
rf = RandomForestClassifier(featuresCol="features", labelCol="isLaundering", numTrees=20, maxDepth=10, maxBins=75)

# Redefine the pipeline with the updated RandomForestClassifier
pipeline = Pipeline(stages=[assembler_final, rf])

"""Hyperparameter Tuning using CrossValidator:

-Used CrossValidator to find the best hyperparameters for the Random Forest model.

-BinaryClassificationEvaluator Used to evaluate the model's performance.

-areaUnderROC is a common metric for binary classification, especially useful for imbalanced datasets.
"""

paramGridSearch = ParamGridBuilder().addGrid(rf.numTrees, [10, 20]).addGrid(rf.maxDepth, [10]).build()
evaluatorr = BinaryClassificationEvaluator(labelCol="isLaundering", metricName="areaUnderROC")
crossvalidation = CrossValidator(estimator=pipeline, estimatorParamMaps=paramGridSearch, evaluator=evaluatorr, numFolds=3)
cvModel = crossvalidation.fit(train_df)

"""Evaluate the Model

Evaluate on Validation Data:

Used F1 Score, Area Under ROC metrics to evaluate the model on validation data.
"""

# Evaluate ROC on validation data
predictions = cvModel.transform(val_df)
roc_score = evaluatorr.evaluate(predictions)
print("Area Under ROC Score on validation data:", roc_score)

# Evaluate F1 Score on validation data
evaluator_f1 = MulticlassClassificationEvaluator(labelCol="isLaundering", predictionCol="prediction", metricName="f1")
f1_score = evaluator_f1.evaluate(predictions)
print("F1 Score on validation data:", f1_score)

"""Final Testing:
Test the model on the test set to get final performance metrics.
"""

# Evaluate ROC on test data
final_predictions = cvModel.transform(test_df)
test_roc_score = evaluatorr.evaluate(final_predictions)
print("Final ROC Score on test data:", test_roc_score)

# Evaluate F1 Score on test data
test_f1_score = evaluator_f1.evaluate(final_predictions)
print("Final F1 Score on test data:", test_f1_score)

#evaluate percision and recall
precision_evaluator = MulticlassClassificationEvaluator(
    labelCol="isLaundering", predictionCol="prediction", metricName="weightedPrecision")
recall_evaluator = MulticlassClassificationEvaluator(
    labelCol="isLaundering", predictionCol="prediction", metricName="weightedRecall")

precision = precision_evaluator.evaluate(final_predictions)
recall = recall_evaluator.evaluate(final_predictions)

print(f"Precision: {precision}")
print(f"Recall: {recall}")

"""Observations

Unrealistically Good Performance, can be caused by

- Data Leakage:
If features or information from the test data inadvertently influenced the training process, the model could appear to perform perfectly. Like Using features directly derived from the target variable. (PatternTypeIndex)

Trying again without PatternTypeIndex
"""

# Define all features for the final assembler, using scaled and unscaled features
all_features = [ "FanOut", "AvgAmountSent", "DayOfWeek", "CurrencyIndex", "PaymentFormatIndex"]

# Assemble the final feature vector for prediction
assembler_final = VectorAssembler(inputCols=all_features, outputCol="features")
balanced_featured_df = balanced_featured_df.select(all_features + ["isLaundering"])

train_df, val_df, test_df = balanced_featured_df.randomSplit([0.6, 0.2, 0.2], seed=42)

rf = RandomForestClassifier(featuresCol="features", labelCol="isLaundering", numTrees=20, maxDepth=10)
pipeline = Pipeline(stages=[ assembler_final, rf])

# Train the model on the training data
rf_model = pipeline.fit(train_df)

# Evaluate on validation data
val_predictions = rf_model.transform(val_df)

# Evaluate ROC on validation data
evaluator = BinaryClassificationEvaluator(labelCol="isLaundering", metricName="areaUnderROC")

paramGridSearch = ParamGridBuilder().addGrid(rf.numTrees, [10]).addGrid(rf.maxDepth, [10]).build()
evaluatorr = BinaryClassificationEvaluator(labelCol="isLaundering", metricName="areaUnderROC")
crossvalidation = CrossValidator(estimator=pipeline, estimatorParamMaps=paramGridSearch, evaluator=evaluatorr, numFolds=2, parallelism=4)
cvModel = crossvalidation.fit(train_df)

# Evaluate ROC on validation data
#predictions = cvModel.transform(val_df)
roc_score = evaluatorr.evaluate(val_predictions)
print("Area Under ROC Score on validation data:", roc_score)

# Evaluate F1 Score on validation data
evaluator_f1 = MulticlassClassificationEvaluator(labelCol="isLaundering", predictionCol="prediction", metricName="f1")
f1_score = evaluator_f1.evaluate(val_predictions)
print("F1 Score on validation data:", f1_score)

# Evaluate ROC on test data
final_predictions = cvModel.transform(test_df)
test_roc_score = evaluatorr.evaluate(final_predictions)
print("Final ROC Score on test data:", test_roc_score)

# Evaluate F1 Score on test data
test_f1_score = evaluator_f1.evaluate(final_predictions)
print("Final F1 Score on test data:", test_f1_score)

#evaluate percision and recall
precision_evaluator = MulticlassClassificationEvaluator(
    labelCol="isLaundering", predictionCol="prediction", metricName="weightedPrecision")
recall_evaluator = MulticlassClassificationEvaluator(
    labelCol="isLaundering", predictionCol="prediction", metricName="weightedRecall")

precision = precision_evaluator.evaluate(final_predictions)
recall = recall_evaluator.evaluate(final_predictions)

print(f"Precision: {precision}")
print(f"Recall: {recall}")

"""Metrics Overview
Validation Data:
Area Under ROC (AUC): 0.927

indicates the model separates positive and negative classes well.

F1 Score: 0.963

Suggests a strong balance between precision and recall on validation data.

Test Data:
Area Under ROC (AUC): 0.928

Similar to validation, indicating consistent performance across datasets.

F1 Score: 0.963

Strong alignment with validation F1, showing generalization capability.

Precision: 0.966

Indicates that 96.6% of the model's positive predictions are correct.

Recall: 0.965

Suggests the model identified 96.5% of actual positive instances.
"""

rf_model = cvModel.bestModel.stages[-1]  # Access the trained Random Forest model
importances = rf_model.featureImportances.toArray()
print("Feature Importances:", importances)

"""Feature Importance

The feature importances are:

DayOfWeek (1st highest): 0.729 (dominant feature)

PaymentFormatIndex (2nd highest): 0.143

AvgAmountSent: 0.063

CurrencyIndex: 0.032

FanOut (least important): 0.030

Analysis: The model relies heavily on DayOfWeek and PaymentFormatIndex, contributing ~87% of the total importance.

Analyze the predictions


to ensure the model is not trivially predicting the majority or minority
"""

# Count predicted classes
final_predictions.groupBy("prediction").count().show()

# Calculate confusion matrix
final_predictions.crosstab("isLaundering", "prediction").show()

"""Observations

True Positives (TP): 617,206 (Correctly identified laundering cases).

True Negatives (TN): 6,292,500 (Correctly identified non-laundering cases).

False Positives (FP): 16,748 (Misclassified non-laundering as laundering).

While relatively low compared to true negatives, false positives could cause unnecessary investigations.

False Negatives (FN): 231,031 (Missed laundering cases).

which could be critical in real-world anti-money laundering applications.
"""

train_df.unpersist()
val_df.unpersist()
test_df.unpersist()