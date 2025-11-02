# PlantE - Mais que no solo

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-black.svg)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-orange.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-blue.svg)
![Redis](https://img.shields.io/badge/Redis-Cloud-red.svg)
![AWS](https://img.shields.io/badge/AWS-Cloud-orange.svg)

API de backend (Flask) para o aplicativo móvel **Plante**. Este serviço gerencia a autenticação de usuários, jardins virtuais, identificação de plantas (via Plant.id), enriquecimento de dados (via Google Gemini), e dispara notificações de cuidado (via Celery/FCM) para uma experiência de cuidado de plantas gamificada e inteligente. <br>
Este documento detalha os endpoints da API REST do Plante App, construída em Flask.

**URL Base:** `/api/v1`

## Autenticação

Quase todos os endpoints da API são protegidos e exigem um JSON Web Token (JWT).

**Fluxo de Autenticação:**

1. O usuário se registra (se for novo) ou faz login.
2. O endpoint `POST /auth/login` retorna um `access_token`.
3. O cliente (app Flutter) deve armazenar este token de forma segura.
4. Para todas as requisições protegidas, o cliente deve enviar o token no cabeçalho (header) HTTP:
    `Authorization: Bearer <seu_token_jwt_aqui>`

Qualquer requisição a um endpoint protegido sem um token válido (ou com um token expirado) retornará um erro `401 Unauthorized`.

-----

## Blueprint: Auth (`/api/v1/auth`)

*Responsável pelo registro, login e gerenciamento de status do usuário.*

### `POST /auth/register`

* **Descrição:** Registra um novo usuário no sistema. O usuário é criado com o status `free` por padrão.
* **Autenticação:** Nenhuma.
* **Corpo da Requisição (JSON):**

    ```json
    {
      "email": "usuario@email.com",
      "password": "senhaforte123"
    }
    ```

* **Resposta (Sucesso `201 Created`):**

    ```json
    {
      "status": "success",
      "data": { "user_id": "uuid-do-novo-usuario" },
      "message": "Usuário registrado com sucesso."
    }
    ```

### `POST /auth/login`

* **Descrição:** Autentica um usuário existente e retorna um token de acesso.
* **Autenticação:** Nenhuma.
* **Corpo da Requisição (JSON):**

    ```json
    {
      "email": "usuario@email.com",
      "password": "senhaforte123"
    }
    ```

* **Resposta (Sucesso `200 OK`):**

    ```json
    {
      "status": "success",
      "data": {
        "token": "ey... (seu_token_jwt_longo)",
        "subscription_status": "free" // ou "premium"
      },
      "message": "Login bem-sucedido."
    }
    ```

### `POST /auth/fcm-token`

* **Descrição:** Salva ou atualiza o token de notificação push (Firebase Cloud Messaging) do dispositivo do usuário. Essencial para os workers enviarem notificações.
* **Autenticação:** `JWT Required`
* **Corpo da Requisição (JSON):**

    ```json
    {
      "fcm_token": "token_do_dispositivo_firebase_aqui"
    }
    ```

* **Resposta (Sucesso `200 OK`):**

    ```json
    {
      "status": "success",
      "data": null,
      "message": "Token do dispositivo atualizado com sucesso."
    }
    ```

### `DELETE /auth/fcm-token`

* **Descrição:** Remove o token FCM do usuário (usado no logout).
* **Autenticação:** `JWT Required`
* **Resposta (Sucesso `200 OK`):**

    ```json
    {
      "status": "success",
      "data": null,
      "message": "Token do dispositivo desvinculado com sucesso."
    }
    ```

### `POST /auth/upgrade-to-premium` (TESTE)

* **Descrição:** Endpoint de **teste** para atualizar o usuário logado para o status `premium` por 30 dias.
* **Autenticação:** `JWT Required`
* **Resposta (Sucesso `200 OK`):**
    ```json
    {
      "status": "success",
      "data": {
        "subscription_status": "premium",
        "expires_at": "2025-11-02T15:00:00.000Z"
      },
      "message": "Usuário atualizado para Premium com sucesso."
    }
    ```

### `POST /auth/revert-to-free` (TESTE)

  * **Descrição:** Endpoint de **teste** para reverter o usuário logado para o status `free`.
  * **Autenticação:** `JWT Required`
  * **Resposta (Sucesso `200 OK`):**
    ```json
    {
      "status": "success",
      "data": { "subscription_status": "free" },
      "message": "Usuário revertido para Free com sucesso."
    }
    ```

-----

## Blueprint: Garden (`/api/v1/garden`)

*Responsável pelo gerenciamento do jardim virtual do usuário.*

### `POST /identify`

  * **Descrição:** Identifica uma planta, cria a entrada no `PlantGuide` (se não existir) e adiciona a planta ao jardim do usuário (`UserPlant`), salvando a URL da imagem de identificação.
  * **Autenticação:** `JWT Required`
  * **Corpo da Requisição (JSON):**
    ```json
    {
      "image": "string_base64_da_imagem_comprimida",
      "latitude": -15.7797,  // Opcional (fallback para o perfil do usuário ou Brasília)
      "longitude": -47.9297 // Opcional
    }
    ```
  * **Resposta (Sucesso `201 Created`):**
    ```json
    {
      "status": "success",
      "data": {
        "user_plant_id": "uuid-da-nova-userplant",
        "nickname": "Hedychium coronarium",
        "scientific_name": "Hedychium coronarium",
        "tracked_watering": false,
        "primary_image_url": "https://plant.id/media/imgs/...",
        "identification_data": { ... (json completo do Plant.id) ... }
      },
      "message": "Planta identificada e adicionada ao seu jardim."
    }
    ```

### `GET /plants`

  * **Descrição:** Retorna a lista de todas as plantas (resumidas) no jardim do usuário logado.
  * **Autenticação:** `JWT Required`
  * **Resposta (Sucesso `200 OK`):**
    ```json
    {
      "status": "success",
      "data": [
        {
          "id": "uuid-planta-1",
          "nickname": "Minha Samambaia",
          "scientific_name": "Nephrolepis exaltata",
          "last_watered": null,
          "tracked_watering": false,
          "primary_image_url": "https://plant.id/media/imgs/..."
        },
        { ... (outra planta) ... }
      ],
      "message": "Jardim carregado com sucesso."
    }
    ```

### `GET /plants/<uuid:plant_id>`

  * **Descrição:** Busca os dados completos de uma planta específica no jardim do usuário.
  * **Autenticação:** `JWT Required`
  * **Resposta (Sucesso `200 OK`):**
    ```json
    {
      "status": "success",
      "data": {
        "id": "uuid-planta-1",
        "nickname": "Minha Samambaia",
        "scientific_name": "Nephrolepis exaltata",
        "added_at": "2025-10-29T18:00:00.000Z",
        "last_watered": null,
        "care_notes": "Deixar longe do sol direto.",
        "tracked_watering": false,
        "primary_image_url": "https://plant.id/media/imgs/...",
        "guide_details": null, // ou { ... json do Gemini ... }
        "guide_nutritional": null, // ou { ... json do Gemini ... }
        "guide_health": null // ou { ... json do Gemini ... }
      },
      "message": "Detalhes da planta carregados."
    }
    ```

### `PUT /plants/<uuid:plant_id>`

  * **Descrição:** Atualiza os dados editáveis de uma planta (apelido, notas, última rega).
  * **Autenticação:** `JWT Required`
  * **Corpo da Requisição (JSON):**
    ```json
    {
      "nickname": "Samambaia Favorita",
      "last_watered": "2025-10-30T10:00:00.000Z", // Formato ISO 8601
      "care_notes": "Adicionado fertilizante."
    }
    ```
  * **Resposta (Sucesso `200 OK`):** Retorna os dados atualizados.

### `DELETE /plants/<uuid:plant_id>`

  * **Descrição:** Remove uma planta do jardim do usuário (não apaga do `PlantGuide`).
  * **Autenticação:** `JWT Required`
  * **Resposta (Sucesso `200 OK`):**
    ```json
    {
      "status": "success",
      "data": null,
      "message": "Planta removida do seu jardim com sucesso."
    }
    ```

### `POST /plants/<uuid:plant_id>/track-watering`

  * **Descrição:** Ativa os lembretes de rega (worker) para esta planta.
  * **Autenticação:** `JWT Required`
  * **Resposta (Sucesso `200 OK`):** `{"data": {"tracked_watering": true}, ...}`

### `DELETE /plants/<uuid:plant_id>/track-watering`

  * **Descrição:** Desativa os lembretes de rega para esta planta.
  * **Autenticação:** `JWT Required`
  * **Resposta (Sucesso `200 OK`):** `{"data": {"tracked_watering": false}, ...}`

### `POST /plants/<uuid:plant_id>/analyze-deep`

  * **Descrição:** **Recurso Premium (Limitado).** Dispara o worker Celery assíncrono para buscar detalhes e dados nutricionais do Gemini.
  * **Autenticação:** `JWT Required`, `check_daily_limit(limit=3)`
  * **Resposta (Sucesso `202 Accepted`):**
    ```json
    {
      "status": "success",
      "data": null,
      "message": "Solicitação de análise profunda recebida. Você será notificado."
    }
    ```

### `POST /plants/<uuid:plant_id>/analyze-health`

  * **Descrição:** **Recurso Premium (Limitado).** Recebe uma *nova imagem* da planta, faz a avaliação de saúde no Plant.id e, se encontrar doença, dispara o worker Celery para buscar o plano de tratamento no Gemini.
  * **Autenticação:** `JWT Required`, `check_daily_limit(limit=3)`
  * **Corpo da Requisição (JSON):**
    ```json
    {
      "image": "string_base64_da_nova_imagem",
      "latitude": -15.7797,
      "longitude": -47.9297
    }
    ```
  * **Resposta (Sucesso `202 Accepted` - Doença encontrada):**
    ```json
    {
      "status": "success",
      "data": { "health_assessment": { ... }, "status": "PENDING_TREATMENT_PLAN" },
      "message": "Doença detectada. Estamos preparando seu plano de tratamento."
    }
    ```
  * **Resposta (Sucesso `200 OK` - Sem Doença):**
    ```json
    {
      "status": "success",
      "data": { "health_assessment": { ... }, "status": "HEALTHY" },
      "message": "Análise de saúde concluída. Nenhuma doença provável detectada."
    }
    ```

-----

## Blueprint: Profile (`/api/v1/profile`)

*Responsável por gerenciar os dados públicos e privados do perfil do usuário.*

### `GET /me`

  * **Descrição:** Busca os dados completos do perfil do usuário logado (para a Tela de Perfil).
  * **Autenticação:** `JWT Required`
  * **Resposta (Sucesso `200 OK`):**
    ```json
    {
      "status": "success",
      "data": {
        "id": "uuid-do-usuario",
        "email": "usuario@email.com",
        "bio": "Amante de plantas!",
        "profile_picture_url": null,
        "country": "Brasil",
        "state": "Santa Catarina",
        "subscription_status": "free",
        "subscription_expires_at": null,
        "watering_streak": 0,
        "created_at": "2025-10-29T17:00:00.000Z"
      },
      "message": "Perfil carregado com sucesso."
    }
    ```

### `PUT /me`

  * **Descrição:** Atualiza os dados editáveis do perfil do usuário (bio, localização).
  * **Autenticação:** `JWT Required`
  * **Corpo da Requisição (JSON):**
    ```json
    {
      "bio": "Minha nova bio.",
      "country": "Brasil",
      "state": "São Paulo"
    }
    ```
  * **Resposta (Sucesso `200 OK`):** Retorna os dados que foram atualizados.
    ```json
    {
      "status": "success",
      "data": {
        "bio": "Minha nova bio.",
        "country": "Brasil",
        "state": "São Paulo",
        "profile_picture_url": null
      },
      "message": "Perfil atualizado com sucesso."
    }
    ```