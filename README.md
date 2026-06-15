# Sabores de Guatemala — Streamlit Cloud

## Ejecutar en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Secretos opcionales

- `HERCULES_API_URL`
- `HERCULES_API_KEY`
- `HERCULES_MODEL` (por defecto: `openai/gpt-5-mini`)

Si no configuras secretos, la app usa respuestas heurísticas locales para mantener la interfaz funcional.

## Nota de adaptación a Streamlit

La especificación original se tradujo a una implementación Streamlit Cloud con:
- Persistencia local en SQLite
- Navegación por secciones en sidebar
- Gráficas con Plotly en lugar de Recharts
- Actualización de estados con controles nativos de Streamlit
