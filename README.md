---
license: N/A
datasets:
  - IBM AML Synthetic Transactions Dataset
library_name: pyspark
language:
  - en
tags:
  - anti-money-laundering
  - big-data
  - distributed-computing
  - pyspark
  - aws
  - random-forest
  - fraud-detection
model-index:
  - name: AML-Detection-RF
    results:
      - task:
          type: classification
        dataset:
          name: IBM AML Synthetic Transactions Dataset
          type: structured
        metrics:
          - name: F1-Score
            type: f1
            value: 0.90
          - name: ROC-AUC
            type: auc
            value: 0.95
---

# **Anti-Money Laundering Detection Using Big Data Technologies**

## **Overview**
Money laundering is a multi-billion-dollar global issue, enabling criminal networks and disrupting economies. This project addresses this challenge by leveraging **Big Data Technologies** to build a robust, scalable, and efficient Anti-Money Laundering (AML) detection system.

Key Features:
- **Scalable Big Data Frameworks**: Built on PySpark and AWS EMR for distributed processing of 3GB transaction data.
- **Machine Learning Model**: Random Forest classifier with high performance on imbalanced datasets.
- **Feature Engineering**: Derived features like `FanIn`, `FanOut`, and `AvgAmountSent` to improve detection.

---

## **Big Data Infrastructure**
![AWS EMR Cluster Setup](path_to_image/aws_emr_cluster_diagram.png)

- **AWS EMR Cluster Configuration**:
  - Primary Node: `1 x m5.xlarge` (4 vCPUs, 16 GiB RAM, 64 GiB EBS)
  - Core Node: `1 x m5.xlarge`
  - Task Nodes: `2 x m5.xlarge`
- **Storage**: Amazon S3 for scalable and reliable data storage.
- **Tools**:
  - **PySpark**: Distributed data processing.
  - **JupyterHub**: Development environment for iterative PySpark coding.

---

## **Exploratory Data Analysis (EDA)**
### Key Insights:
#### **Severe Class Imbalance**
![Class Imbalance](path_to_image/class_imbalance_chart.png)
- 99.95% transactions are non-laundering, 0.05% are laundering.

#### **Payment Format Distribution**
![Payment Format Distribution](path_to_image/payment_format_distribution_chart.png)
- Most common: Cheque and Credit Card.
- Least common: Bitcoin and Wire Transfers.

#### **Feature Correlation**
![Feature Correlation Heatmap](path_to_image/feature_correlation_heatmap.png)
- Features like `PatternTypeIndex` had a high correlation (0.68) with laundering.

---

## **Data Preprocessing**
1. **Feature Engineering**:
   - Extracted temporal features like `hour` and `day_of_week`.
   - Derived features: `FanIn`, `FanOut`, `AvgAmountSent`.
2. **Data Imbalance Handling**:
   - Downsampled the majority class (non-laundering transactions).
   - Applied SMOTE (Synthetic Minority Oversampling).
   - **Balanced Dataset Visualization**:
     ![SMOTE Class Distribution](path_to_image/smote_class_distribution_chart.png)

---

## **Model Selection**
- **Chosen Model**: Random Forest (RF)
- **Reasons for Selection**:
  - Handles imbalanced datasets effectively.
  - Provides feature importance insights.
  - Scales well with distributed systems.
 
### **Training and Evaluation**
- **Training Configuration**:
  - Features: `FanOut`, `FanIn`, `AvgAmountSent`, `Hour`, `DayOfWeek`, `CurrencyIndex`, `PaymentFormatIndex`.
  - Hyperparameters: 
    - Trees: 20
    - Max Depth: 10
    - Max Bins: 75
  - Data Split: 70% training, 15% validation, 15% test.
- **Second Run (after addressing data leakage)**:
  - F1-Score: **0.90**
  - ROC-AUC: **0.95**
  - Precision: **0.97**
  - Recall: **0.98**

---

## **Performance Metrics**
| Metric        | First Run (With Leakage) | Second Run (No Leakage) |
|---------------|---------------------------|--------------------------|
| F1-Score      | 1.0                       | 0.90                    |
| ROC-AUC       | 1.0                       | 0.95                    |
| Precision     | 1.0                       | 0.97                    |
| Recall        | 1.0                       | 0.98                    |

### **Performance Comparison**
![Performance Comparison](path_to_image/performance_comparison_chart.png)

### **Confusion Matrix**
![Confusion Matrix](path_to_image/confusion_matrix.png)

---

## **Confusion Matrix**
- **True Positives (TP)**: Correctly identified laundering transactions.
- **False Negatives (FN)**: Missed laundering cases.
- **False Positives (FP)**: Legitimate transactions incorrectly flagged.
- **True Negatives (TN)**: Correctly identified legitimate transactions.

---

## **Conclusion**
This project successfully demonstrated how distributed systems and machine learning can handle large-scale financial data for fraud detection. Key achievements include:
- Scalable infrastructure with AWS EMR and PySpark.
- Robust Random Forest model with realistic performance metrics.
- Addressing data leakage and class imbalance for reliable results.

---

## **Future Work**
1. Experiment with advanced models like XGBoost and GNNs.
2. Incorporate cross-validation for robust hyperparameter tuning.
3. Optimize the AWS EMR cluster for cost-efficiency.
4. Expand feature engineering with domain-specific insights.

---

## **How to Use**
### **Setup Instructions**
1. Clone the repository:
   ```bash
   git clone https://github.com/kashyaparun/Anti-Money-Laundering-Detection.git
