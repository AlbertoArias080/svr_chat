# Proyecto Flask (Web App)

Aplicación web desarrollada con **Python + Flask** y frontend en **HTML/CSS**.  
El proyecto usa variables de entorno en `.env` y dependencias en `requirements.txt`.

---

## 🚀 Tecnologías usadas
- Python
- Flask
- HTML / CSS
- Virtualenv (`.venv`)

---

## 📁 Estructura del proyecto

.
│ .env
│ .gitignore
│ check_setup.py
│ config.py
│ list_users.py
│ requirements.txt
│ run.py
│
└─.venv/



---

## ✅ Requisitos previos
- Tener instalado **Python** (idealmente 3.10+).
- Tener `pip` disponible.
- (Opcional) Git para clonar el repositorio.

---

## ⚙️ Instalación

### 1) Clonar el repositorio
```bash
git clone https://github.com/AlbertoArias080/svr_chat.git
cd svr_chat
2) Crear entorno virtual
Windows


python -m venv .venv
.venv\Scripts\activate

3) Instalar dependencias

pip install -r requirements.txt
Dependencias principales incluidas:

Flask

Flask-WTF

Flask-Login

boto3

python-dotenv
(Ver requirements.txt para el detalle.)

▶️ Ejecución
Activa tu entorno virtual (si no lo está).

Ejecuta:


python run.py



http://127.0.0.1:5000
Abre esa dirección en tu navegador.

🔐 Variables de entorno (.env)
El proyecto incluye un archivo .env en la raíz.

🧪 Scripts útiles


config.py: configuración central del proyecto.

🛠️ Problemas comunes
1. “ModuleNotFoundError”

Asegúrate de tener el entorno virtual activado.

Reinstala dependencias:


pip install -r requirements.txt
2. Puerto ocupado

Si el puerto 5000 está ocupado, puedes cambiarlo en run.py o ejecutar:


flask --app run.py run --port 5001