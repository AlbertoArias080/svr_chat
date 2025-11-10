from app import create_app

app = create_app()

if __name__ == '__main__':
    print("Rutas registradas:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.endpoint}: {rule.rule}")
    print("\nIniciando servidor...")
    app.run(debug=True, host='0.0.0.0', port=5000)