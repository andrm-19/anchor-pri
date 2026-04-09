Anchor App Backend API (v1.3)

API backend para la aplicación Anchor, encargada de la gestión de usuarios, autenticación y lógica de negocio.
Por: David Felipe Rodriguez Sierra 

PRI1 - ICIB

Tecnologías utilizadas:

    -Python 3.x

    -FastAPI – Framework para construir la API

    -SQLite – Base de datos ligera local

    -Pydantic – Validación de datos de entrada

    -bcrypt – Hash de contraseñas

    -JWT (JSON Web Tokens) – Autenticación segura


Funcionalidades:

    -Registro de usuario (POST /register)

Crea un nuevo usuario con:

    -username (único)
    
    -password (contraseña segura)


Validación de contraseña:

    -Al menos 8 caracteres

    -Al menos una letra mayúscula

    -Al menos una letra minúscula

    -Al menos un número

Respuesta exitosa:

    {"message": "Usuario registrado exitosamente"}

Errores posibles:

    Usuario ya existe

    Contraseña débil


Inicio de sesión (POST /login)

Permite que un usuario existente inicie sesión con:

    username

    password

Retorna un token JWT en caso de éxito:

    {"access_token": "<token_jwt>", "token_type": "bearer"}

Errores posibles:

    Credenciales inválidas

Listar usuarios (GET /users)

Devuelve un listado de todos los usuarios registrados:

    {"users": ["usuario1", "usuario2"]}

Home (GET /)

Mensaje de bienvenida para verificar que la API está funcionando:

    {"message": "ZenMode API en ejecucion..."}

Base de datos

Base de datos SQLite: users.db

Tabla users con campos:

    id – INTEGER PRIMARY KEY AUTOINCREMENT

    username – TEXT único, obligatorio

    password – TEXT, obligatorio (almacenado con hash bcrypt)

Funciones principales:

    -init_db() – Inicializa la base de datos y la tabla users

    -get_user(username) – Obtiene datos de un usuario

    -add_user(username, hashed_password) – Añade un nuevo usuario

    -list_all_users() – Lista todos los usuarios

Autenticación

    Tokens JWT creados con clave secreta (SECRET_KEY) y algoritmo HS256

    Expiración: 60 minutos por defecto (ACCESS_TOKEN_EXPIRE_MINUTES)

    Middleware verify_token valida el token para endpoints protegidos


Instalación

    1. git clone https://github.com/davidlaught333-eng/Anchor-Backend.git

    2. cd anchor-app-backend

    3. python -m venv venv

    4. source venv/bin/activate # Windows: venv\Scripts\activate

    5. pip install fastapi uvicorn bcrypt python-jose pydantic


Configuración

Archivo .env (opcional):

    SECRET_KEY=supersecretkey

    ACCESS_TOKEN_EXPIRE_MINUTES=60

    DB_FILE=users.db

Ejecución

    uvicorn app.main:app --reload

    La API estará disponible en http://localhost:8000

Modelos de datos

    UserRegister (Pydantic)

      username: str
      password: str

    UserLogin (Pydantic)

      username: str
      password: str
