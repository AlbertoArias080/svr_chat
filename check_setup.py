#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models import DynamoDB

def init_chat_table():
    print("💬 INICIALIZANDO TABLA DE CHAT")
    print("=" * 40)
    
    try:
        db = DynamoDB()
        db.create_chat_table()
        print("✅ Tabla de chat inicializada")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    init_chat_table()