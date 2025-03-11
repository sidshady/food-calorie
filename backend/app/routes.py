from fastapi import APIRouter, UploadFile, File, HTTPException
import boto3
import httpx
from .config import (
    AWS_ACCESS_KEY_ID, 
    AWS_SECRET_ACCESS_KEY, 
    AWS_REGION,
    NUTRITIONIX_APP_ID,
    NUTRITIONIX_API_KEY,
    NUTRITIONIX_API_ENDPOINT
)
from typing import Dict, List
import base64

router = APIRouter()

rekognition_client = boto3.client(
    'rekognition',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

async def get_enhanced_nutrition_info(food_item: str) -> Dict:
    """Get calorie information from Nutritionix API."""
    headers = {
        "x-app-id": NUTRITIONIX_APP_ID,
        "x-app-key": NUTRITIONIX_API_KEY,
        "Content-Type": "application/json"
    }
    
    data = {
        "query": food_item,
        "timezone": "US/Eastern"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                NUTRITIONIX_API_ENDPOINT,
                json=data,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            if "foods" in data and len(data["foods"]) > 0:
                food = data["foods"][0]
                return {
                    "food_name": food.get("food_name", ""),
                    "calories": food.get("nf_calories", 0),
                    "serving_qty": food.get("serving_qty", 1),
                    "serving_unit": food.get("serving_unit", "serving")
                }
        except Exception as e:
            print(f"Error fetching nutrition info for {food_item}: {str(e)}")
            return None

@router.post("/analyze-food")
async def analyze_food(file: UploadFile = File(...)):
    contents = await file.read()
    
    try:
        response = rekognition_client.detect_labels(
            Image={'Bytes': contents},
            MaxLabels=20,
            MinConfidence=60
        )
        
        food_items = []
        total_calories = 0
        
        food_labels = [label for label in response['Labels'] 
                      if any(category['Name'] in ['Food', 'Drink', 'Beverage'] 
                            for category in label.get('Categories', []))]
        
        if not food_labels:
            food_labels = response['Labels']
        
        for label in food_labels:
            label_name = label['Name'].lower()
            nutrition_info = await get_enhanced_nutrition_info(label_name)
            
            if nutrition_info:
                food_item = {
                    'name': label_name,
                    'confidence': label['Confidence'],
                    'calories': nutrition_info["calories"],
                    'serving_info': f"{nutrition_info['serving_qty']} {nutrition_info['serving_unit']}"
                }
                
                food_items.append(food_item)
                total_calories += nutrition_info["calories"]
        
        return {
            'food_items': food_items,
            'total_calories': total_calories,
            'success': True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))