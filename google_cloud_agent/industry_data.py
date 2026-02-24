"""
Google Cloud Industry Solutions Knowledge Base

Comprehensive industry-specific information for the Discovery Agent.
Includes use cases, solutions, and GCP services relevant to each industry.
"""

INDUSTRY_DATA = {
    "financial_services": {
        "description": "Banking, insurance, investment management, and fintech",
        "key_challenges": [
            "Regulatory compliance (PCI-DSS, HIPAA, SOC 2)",
            "Fraud detection and prevention",
            "Real-time transaction processing",
            "Legacy system modernization",
            "Data privacy and encryption",
            "High availability requirements"
        ],
        "gcp_solutions": {
            "fraud_detection": {
                "description": "Detect fraudulent transactions in real-time",
                "services": ["Vertex AI", "BigQuery", "Pub/Sub", "Dataflow"],
                "use_case": "Real-time ML model scoring on transaction streams"
            },
            "compliance": {
                "description": "Maintain regulatory compliance and audit trails",
                "services": ["Cloud Logging", "Cloud Audit Logs", "KMS", "VPC"],
                "use_case": "Centralized logging with encryption and access controls"
            },
            "data_warehouse": {
                "description": "Consolidate financial data for analytics",
                "services": ["BigQuery", "Looker", "Data Studio"],
                "use_case": "Real-time analytics on historical and transactional data"
            },
            "microservices": {
                "description": "Modernize monolithic applications",
                "services": ["GKE", "Cloud Run", "Service Mesh", "API Gateway"],
                "use_case": "Containerized microservices with managed orchestration"
            }
        },
        "recommended_gcp_products": [
            "BigQuery", "Vertex AI", "Cloud KMS", "GKE", "Cloud Armor",
            "Pub/Sub", "Dataflow", "Looker"
        ]
    },
    
    "retail": {
        "description": "E-commerce, physical retail, supply chain, and omnichannel",
        "key_challenges": [
            "Inventory management across channels",
            "Customer experience personalization",
            "Real-time demand forecasting",
            "Supply chain visibility",
            "Seasonal demand spikes",
            "Global expansion"
        ],
        "gcp_solutions": {
            "personalization": {
                "description": "Personalized product recommendations",
                "services": ["Vertex AI Recommendation Engine", "BigQuery", "Memorystore"],
                "use_case": "ML-powered recommendations based on browsing and purchase history"
            },
            "inventory": {
                "description": "Optimize inventory across all channels",
                "services": ["BigQuery", "Vertex AI", "Dataflow"],
                "use_case": "Real-time inventory optimization using demand forecasting"
            },
            "supply_chain": {
                "description": "End-to-end supply chain visibility",
                "services": ["Cloud SQL", "Pub/Sub", "Maps Platform", "Looker"],
                "use_case": "Track shipments, predict delays, optimize routes"
            },
            "customer_analytics": {
                "description": "360-degree customer view",
                "services": ["BigQuery", "Dataflow", "Looker", "Customer Insights"],
                "use_case": "Unified customer profiles for cross-channel marketing"
            }
        },
        "recommended_gcp_products": [
            "BigQuery", "Vertex AI", "Pub/Sub", "Dataflow", "Looker",
            "GKE", "Cloud CDN", "Cloud Armor"
        ]
    },
    
    "healthcare": {
        "description": "Hospitals, clinics, pharmaceutical, medical devices, telemedicine",
        "key_challenges": [
            "HIPAA and healthcare regulations",
            "Patient data privacy",
            "Interoperability between systems",
            "Real-time patient monitoring",
            "Drug discovery acceleration",
            "Telemedicine infrastructure"
        ],
        "gcp_solutions": {
            "patient_data": {
                "description": "Secure patient data management",
                "services": ["Cloud Healthcare API", "Cloud KMS", "VPC", "Cloud Audit Logs"],
                "use_case": "HIPAA-compliant patient record management"
            },
            "ai_diagnostics": {
                "description": "AI-powered diagnostic imaging analysis",
                "services": ["Vertex AI", "Healthcare Natural Language API", "Document AI"],
                "use_case": "ML models for X-ray, CT, and MRI analysis"
            },
            "genomics": {
                "description": "Genomic research and drug discovery",
                "services": ["BigQuery", "Dataflow", "Vertex AI", "Life Sciences API"],
                "use_case": "Process and analyze massive genomic datasets"
            },
            "telemedicine": {
                "description": "Secure video consultations",
                "services": ["WebRTC Insertable Streams", "Cloud Run", "Cloud Load Balancing"],
                "use_case": "HIPAA-compliant telemedicine platform"
            }
        },
        "recommended_gcp_products": [
            "Cloud Healthcare API", "Vertex AI", "BigQuery", "Cloud KMS",
            "Cloud Run", "Dataflow", "Document AI", "Healthcare Natural Language API"
        ]
    },
    
    "manufacturing": {
        "description": "Industrial, automotive, electronics, smart factories",
        "key_challenges": [
            "Predictive maintenance",
            "Equipment downtime",
            "Quality control",
            "Production optimization",
            "Supply chain integration",
            "Worker safety"
        ],
        "gcp_solutions": {
            "predictive_maintenance": {
                "description": "Prevent equipment failures before they occur",
                "services": ["Vertex AI", "BigQuery", "Pub/Sub", "IoT Core"],
                "use_case": "ML models trained on sensor data to predict failures"
            },
            "quality_control": {
                "description": "Automated quality inspection with computer vision",
                "services": ["Vertex AI Vision", "Document AI", "GKE"],
                "use_case": "Real-time defect detection on production line"
            },
            "production_optimization": {
                "description": "Optimize production schedules and resource allocation",
                "services": ["Vertex AI", "BigQuery", "Dataflow"],
                "use_case": "ML-driven production scheduling"
            },
            "iot_infrastructure": {
                "description": "Connect and manage factory floor devices",
                "services": ["Cloud IoT Core", "Pub/Sub", "Dataflow", "BigQuery"],
                "use_case": "Real-time monitoring of machine sensors"
            }
        },
        "recommended_gcp_products": [
            "Vertex AI", "Cloud IoT Core", "BigQuery", "Pub/Sub", "Dataflow",
            "GKE", "Cloud SQL", "Document AI"
        ]
    },
    
    "media_entertainment": {
        "description": "Content creation, streaming, gaming, sports",
        "key_challenges": [
            "Content delivery at scale",
            "Live streaming reliability",
            "Content recommendation",
            "Licensing and rights management",
            "Global content distribution",
            "User engagement analytics"
        ],
        "gcp_solutions": {
            "content_delivery": {
                "description": "Deliver content globally with low latency",
                "services": ["Cloud CDN", "Media CDN", "Cloud Load Balancing"],
                "use_case": "High-performance video streaming to millions"
            },
            "live_streaming": {
                "description": "Reliable live event streaming",
                "services": ["Transcoder API", "Cloud Pub/Sub", "Cloud Run"],
                "use_case": "Real-time transcoding and distribution"
            },
            "recommendations": {
                "description": "Recommend content based on viewing patterns",
                "services": ["Vertex AI Recommendation Engine", "BigQuery"],
                "use_case": "Personalized content recommendations"
            },
            "game_infrastructure": {
                "description": "Multiplayer game backend",
                "services": ["Agones", "GKE", "Cloud Firestore", "Realtime Database"],
                "use_case": "Scalable game server infrastructure"
            }
        },
        "recommended_gcp_products": [
            "Cloud CDN", "Media CDN", "Vertex AI", "BigQuery", "Cloud Run",
            "GKE", "Agones", "Transcoder API"
        ]
    },
    
    "energy_utilities": {
        "description": "Electric utilities, oil/gas, renewable energy, water",
        "key_challenges": [
            "Grid management and optimization",
            "Demand forecasting",
            "Equipment monitoring",
            "Regulatory compliance",
            "Smart meter infrastructure",
            "Asset management"
        ],
        "gcp_solutions": {
            "grid_optimization": {
                "description": "Balance supply and demand in real-time",
                "services": ["Vertex AI", "BigQuery", "Pub/Sub", "Cloud IoT"],
                "use_case": "ML-powered grid load balancing"
            },
            "demand_forecasting": {
                "description": "Predict energy demand with high accuracy",
                "services": ["Vertex AI Forecasting", "BigQuery", "Dataflow"],
                "use_case": "Hourly to seasonal demand prediction"
            },
            "asset_monitoring": {
                "description": "Monitor equipment health and performance",
                "services": ["Cloud IoT Core", "Pub/Sub", "Dataflow", "BigQuery"],
                "use_case": "Real-time monitoring of power plants and substations"
            },
            "renewable_integration": {
                "description": "Integrate renewable energy sources",
                "services": ["Vertex AI", "BigQuery", "Weather API"],
                "use_case": "Forecast solar/wind generation based on weather"
            }
        },
        "recommended_gcp_products": [
            "Vertex AI", "BigQuery", "Cloud IoT Core", "Pub/Sub", "Dataflow",
            "Cloud SQL", "Maps API", "Cloud Monitoring"
        ]
    },
    
    "telecommunications": {
        "description": "Telecom operators, ISP, mobile networks, connectivity",
        "key_challenges": [
            "Network optimization",
            "Customer churn prediction",
            "5G infrastructure",
            "Network monitoring",
            "Customer billing",
            "Capacity planning"
        ],
        "gcp_solutions": {
            "network_optimization": {
                "description": "Optimize network performance and reduce congestion",
                "services": ["Vertex AI", "BigQuery", "Network Intelligence"],
                "use_case": "ML-driven traffic engineering"
            },
            "churn_prediction": {
                "description": "Predict and prevent customer churn",
                "services": ["Vertex AI", "BigQuery", "Dataflow"],
                "use_case": "Early intervention for at-risk customers"
            },
            "5g_infrastructure": {
                "description": "Build scalable 5G network infrastructure",
                "services": ["GKE", "Anthos", "Cloud Run", "Service Mesh"],
                "use_case": "Containerized 5G core network functions"
            },
            "network_monitoring": {
                "description": "Real-time network performance monitoring",
                "services": ["Cloud Monitoring", "Cloud Trace", "Cloud Logging"],
                "use_case": "Comprehensive network visibility and alerting"
            }
        },
        "recommended_gcp_products": [
            "Vertex AI", "BigQuery", "GKE", "Anthos", "Cloud Run",
            "Pub/Sub", "Cloud Monitoring", "Network Intelligence"
        ]
    },
    
    "government": {
        "description": "Federal, state, local government, public sector",
        "key_challenges": [
            "Data security and compliance",
            "Government regulations",
            "Citizen services",
            "Interagency data sharing",
            "Budget constraints",
            "Legacy system modernization"
        ],
        "gcp_solutions": {
            "data_analytics": {
                "description": "Analyze government data for insights",
                "services": ["BigQuery", "Looker", "Data Studio"],
                "use_case": "Public data analytics and reporting"
            },
            "citizen_services": {
                "description": "Improve citizen-facing digital services",
                "services": ["Cloud Run", "Cloud SQL", "Cloud Identity"],
                "use_case": "Scalable, secure government portals"
            },
            "compliance": {
                "description": "Meet FedRAMP and FISMA requirements",
                "services": ["GKE", "Cloud KMS", "Cloud Armor", "VPC"],
                "use_case": "Compliant cloud infrastructure for government"
            },
            "interagency_sharing": {
                "description": "Securely share data across agencies",
                "services": ["BigQuery", "Cloud Data Fusion", "Cloud DLP"],
                "use_case": "Federated data sharing with privacy controls"
            }
        },
        "recommended_gcp_products": [
            "BigQuery", "Looker", "Cloud Run", "GKE", "Cloud KMS",
            "Cloud Armor", "Cloud Identity", "Cloud DLP"
        ]
    },
    
    "education": {
        "description": "K-12, higher education, edtech, online learning",
        "key_challenges": [
            "Online learning platforms",
            "Student engagement",
            "Personalized learning",
            "Assessment and grading",
            "Accessibility",
            "Student data privacy (FERPA)"
        ],
        "gcp_solutions": {
            "learning_platform": {
                "description": "Scalable online learning infrastructure",
                "services": ["Cloud Run", "GKE", "Cloud SQL", "Cloud Storage"],
                "use_case": "Multi-tenant education platform"
            },
            "personalization": {
                "description": "Personalize learning paths",
                "services": ["Vertex AI", "BigQuery", "Dataflow"],
                "use_case": "Adaptive learning based on student performance"
            },
            "analytics": {
                "description": "Analyze student learning outcomes",
                "services": ["BigQuery", "Looker", "Data Studio"],
                "use_case": "Student success analytics and early intervention"
            },
            "accessibility": {
                "description": "Make content accessible to all students",
                "services": ["Document AI", "Speech-to-Text", "Text-to-Speech"],
                "use_case": "Automatic captions and accessibility services"
            }
        },
        "recommended_gcp_products": [
            "Cloud Run", "GKE", "BigQuery", "Vertex AI", "Cloud Storage",
            "Looker", "Document AI", "Speech-to-Text"
        ]
    }
}

def get_industry_info(industry_name: str) -> dict:
    """
    Retrieve comprehensive information about a specific industry.
    
    Args:
        industry_name: Name of the industry (normalized to lowercase with underscores)
        
    Returns:
        Dictionary containing industry information, or None if not found
    """
    normalized_name = industry_name.lower().replace(" ", "_").replace("-", "_")
    return INDUSTRY_DATA.get(normalized_name)


def list_industries() -> list:
    """Get a list of all available industries."""
    return [
        name.replace("_", " ").title()
        for name in INDUSTRY_DATA.keys()
    ]


def get_gcp_products_for_industry(industry_name: str) -> list:
    """Get recommended GCP products for a specific industry."""
    industry_info = get_industry_info(industry_name)
    if industry_info:
        return industry_info.get("recommended_gcp_products", [])
    return []


def get_solutions_by_challenge(industry_name: str) -> dict:
    """Map industry challenges to relevant GCP solutions."""
    industry_info = get_industry_info(industry_name)
    if not industry_info:
        return {}
    
    result = {}
    challenges = industry_info.get("key_challenges", [])
    solutions = industry_info.get("gcp_solutions", {})
    
    for solution_name, solution_data in solutions.items():
        result[solution_name] = {
            "description": solution_data.get("description"),
            "services": solution_data.get("services", []),
            "use_case": solution_data.get("use_case")
        }
    
    return result
