#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models import DynamoDB

def list_all_users():
    db = DynamoDB()
    users = db.list_users()
    
    print("📊 USUARIOS REGISTRADOS EN DYNAMODB")
    print("=" * 80)
    
    if not users:
        print("❌ No hay usuarios registrados")
        return
    
    for i, user in enumerate(users, 1):
        print(f"\n👤 Usuario #{i}")
        print(f"   Email: {user.email}")
        print(f"   Rol: {user.role}")
        print(f"   ID: {user.id}")
        print(f"   Creado: {user.created_at}")
        print("-" * 40)

if __name__ == '__main__':
    list_all_users()