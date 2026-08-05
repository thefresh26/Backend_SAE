# Vista_inmuebles_SAE — backend

Versión con backend intermedio (Flask). El navegador ya no habla directo
con Supabase: solo con este servidor. El ID del proyecto Supabase, la anon
key y la service_role key nunca llegan al navegador.

## Cómo desplegarlo (Render, plan gratis)

1. Sube esta carpeta a un repositorio de GitHub (nuevo repo o subcarpeta).
2. En Render: New → Web Service → conecta el repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
3. En Settings → Environment, agrega:
   - `SECRET_KEY` (cualquier cadena larga aleatoria)
   - `SUPABASE_URL` (la misma que usa el visor actual)
   - `SUPABASE_ANON_KEY` (la misma anon key actual)
   - `SUPABASE_SERVICE_ROLE_KEY` (Supabase → Settings → API → service_role;
     NUNCA la subas al repo)
4. Antes de usarlo, ejecuta en Supabase (SQL Editor) el archivo
   `09_ajuste_logs_backend.sql` (además del `08_endurecer_sae.sql` que ya
   corriste en el proyecto original).

## Probar en local

```
pip install -r requirements.txt
set SECRET_KEY=dev
set SUPABASE_URL=https://tu-proyecto.supabase.co
set SUPABASE_ANON_KEY=...
set SUPABASE_SERVICE_ROLE_KEY=...
python app.py
```

Abre http://localhost:5000
