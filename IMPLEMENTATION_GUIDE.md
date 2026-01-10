# Guia de Implementação - Plataforma de Agentes de IA

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura Refatorada](#arquitetura-refatorada)
3. [Segurança Implementada](#segurança-implementada)
4. [Transparência e Logging](#transparência-e-logging)
5. [Eficiência da IA](#eficiência-da-ia)
6. [Guia de Integração](#guia-de-integração)
7. [Checklist de Implementação](#checklist-de-implementação)

---

## Visão Geral

Esta refatoração implementa as 3 pilares críticos para produção:

### 🔒 SEGURANÇA
- ✅ Hashing de senhas com bcrypt
- ✅ Remoção de dados sensíveis de metadados
- ✅ Rate limiting contra ataques
- ✅ Verificação de email
- ✅ Transações atômicas

### 📊 TRANSPARÊNCIA
- ✅ Logging completo de chamadas de IA
- ✅ Rastreamento de fontes (Answer Sources)
- ✅ Dashboard de custos
- ✅ Auditoria de ações

### ⚡ EFICIÊNCIA
- ✅ Busca por embeddings (RAG)
- ✅ Prompt otimizado com estrutura XML
- ✅ Caching com Redis
- ✅ Retry com exponential backoff
- ✅ Sliding window de histórico

---

## Arquitetura Refatorada

### Estrutura de Diretórios

```
src/
├── backend/
│   ├── services/
│   │   ├── SecurityService.ts          # Hashing, validação, sanitização
│   │   ├── OptimizedPromptBuilder.ts   # Construção de prompts XML
│   │   ├── EmbeddingSearchService.ts   # Busca por embeddings
│   │   ├── CacheService.ts             # Cache com Redis
│   │   └── MessageProcessorService.ts  # Processamento refatorado
│   ├── logger/
│   │   └── AICallLogger.ts             # Logging de IA e auditoria
│   ├── middleware/
│   │   └── RateLimitMiddleware.ts      # Rate limiting
│   ├── routers/
│   │   ├── authRouter.ts               # Autenticação segura
│   │   ├── agentRouter.ts              # Gerenciamento de agentes
│   │   └── messageRouter.ts            # Processamento de mensagens
│   └── db/
│       └── schema.ts                   # Schema atualizado
├── frontend/
│   ├── pages/
│   └── components/
└── shared/
    └── types.ts
```

### Fluxo de Processamento de Mensagem

```
1. RECEBER MENSAGEM
   ↓
2. VALIDAR ENTRADA (SecurityService)
   ↓
3. BUSCAR AGENTE E CONVERSA
   ↓
4. BUSCAR HISTÓRICO (sliding window)
   ↓
5. BUSCAR TRAININGS RELEVANTES (EmbeddingSearchService)
   ↓
6. CONSTRUIR PROMPT (OptimizedPromptBuilder)
   ↓
7. CHAMAR LLM COM RETRY (MessageProcessorService)
   ↓
8. EXTRAIR SOURCES E VALIDAR QUALIDADE
   ↓
9. REGISTRAR LOG DE IA (AICallLogger)
   ↓
10. SALVAR MENSAGEM COM SOURCES
   ↓
11. ATUALIZAR CRÉDITOS
   ↓
12. RETORNAR RESPOSTA
```

---

## Segurança Implementada

### 1. Hashing de Senhas

**Antes (INSEGURO):**
```typescript
const user = await db.createUser({
  password: input.password, // ❌ Texto plano
});
```

**Depois (SEGURO):**
```typescript
const hashedPassword = await SecurityService.hashPassword(input.password);
const user = await db.createUser({
  password: hashedPassword, // ✅ Hash com bcrypt
});
```

### 2. Verificação de Senha

```typescript
const isValid = await SecurityService.verifyPassword(
  inputPassword,
  storedHash
);
```

### 3. Sanitização de Dados Sensíveis

**Antes (INSEGURO):**
```typescript
// Enviando senha para Mercado Pago
const metadata = {
  userPassword: input.userPassword, // ❌ EXPOSTO
  userEmail: input.userEmail,
};
```

**Depois (SEGURO):**
```typescript
const metadata = SecurityService.sanitizeForThirdParty({
  userPassword: input.userPassword,
  userEmail: input.userEmail,
  // Resultado: { userEmail: input.userEmail } - senha removida
});
```

### 4. Rate Limiting

```typescript
// Aplicar em routers
import { setupRateLimiters } from './middleware/RateLimitMiddleware';

const limiters = setupRateLimiters();

app.post('/auth/login', limiters.login.middleware(), authRouter.login);
app.post('/auth/signup', limiters.signup.middleware(), authRouter.signup);
app.post('/messages/send', limiters.sendMessage.middleware(), messageRouter.send);
```

### 5. Verificação de Email

```typescript
// Signup envia token
const emailVerificationToken = SecurityService.generateSecureToken();

// Usuário clica no link
await authRouter.verifyEmail({ token: emailVerificationToken });

// Só depois pode fazer login
```

---

## Transparência e Logging

### 1. Logging de Chamadas de IA

```typescript
await AICallLogger.logLLMCall({
  userId: params.userId,
  agentId: params.agentId,
  model: 'gpt-4o',
  duration: 1250, // ms
  tokensUsed: 342,
  creditsUsed: 0.03,
  status: 'success',
  responseQuality: {
    score: 85,
    issues: [],
    suggestions: [],
  },
});
```

**Dados Registrados:**
- Prompt enviado (comprimento)
- Resposta recebida (comprimento)
- Tokens utilizados
- Créditos consumidos
- Duração da chamada
- Score de qualidade
- Status (sucesso/erro/timeout)
- IP e User-Agent

### 2. Rastreamento de Fontes

```typescript
await AICallLogger.logAnswerSources(messageId, [
  {
    type: 'training',
    title: 'Política de Reembolso',
    excerpt: 'Oferecemos reembolso em até 30 dias...',
    relevanceScore: 95,
    usedInResponse: true,
  },
], confidence: 92);
```

### 3. Dashboard de Transparência

**Endpoint:**
```typescript
GET /api/trpc/transparency.getLLMCalls?agentId=123
```

**Resposta:**
```json
{
  "logs": [
    {
      "id": "log-001",
      "model": "gpt-4o",
      "duration": 1250,
      "tokensUsed": 342,
      "creditsUsed": 0.03,
      "status": "success",
      "qualityScore": 85,
      "createdAt": "2026-01-10T10:30:00Z"
    }
  ],
  "costStats": {
    "totalCreditsUsed": 125.50,
    "avgCostPerMessage": 0.42,
    "totalMessages": 298,
    "avgQualityScore": 87,
    "errorRate": 2.3
  }
}
```

---

## Eficiência da IA

### 1. Busca por Embeddings (RAG)

**Antes (INEFICIENTE):**
```typescript
// Incluir TODOS os treinamentos no prompt
const prompt = `
Contexto:
${allTrainings.map(t => t.content).join('\n')}

Pergunta: ${userMessage}
`;
// Resultado: 50,000+ tokens!
```

**Depois (EFICIENTE):**
```typescript
// Buscar apenas os 5 mais relevantes
const relevantTrainings = await EmbeddingSearchService.findRelevantTrainings(
  agentId,
  userMessage,
  topK: 5
);

const prompt = buildOptimizedPrompt({
  trainings: relevantTrainings, // Apenas 5
});
// Resultado: 2,000 tokens - 96% de economia!
```

### 2. Prompt Otimizado com Estrutura XML

```xml
<?xml version="1.0" encoding="UTF-8"?>
<task>
  <objective>
    Você é Atendente, um agente especialista em suporte.
  </objective>
  
  <knowledge_base>
    <document title="Política de Reembolso">
      Oferecemos reembolso em até 30 dias...
    </document>
  </knowledge_base>
  
  <conversation_history>
    <message from="Cliente">Qual é a política de reembolso?</message>
  </conversation_history>
  
  <few_shot_examples>
    <example>
      <user_message>Não consigo fazer login</user_message>
      <expected_response>Entendo. Qual é a mensagem de erro?</expected_response>
    </example>
  </few_shot_examples>
  
  <rules_and_constraints>
    <rule priority="critical">Responda em máximo 4 linhas</rule>
    <rule priority="critical">NUNCA invente informações</rule>
  </rules_and_constraints>
  
  <current_message_to_respond>
    <from>Cliente</from>
    <text>Qual é a política de reembolso?</text>
  </current_message_to_respond>
</task>
```

### 3. Caching com Redis

```typescript
// Primeiro acesso - gera prompt
const prompt = buildOptimizedPrompt(context);
await cache.setCachedPrompt(agentId, trainingIds, prompt);

// Próximos acessos - busca do cache
const cachedPrompt = await cache.getCachedPrompt(agentId, trainingIds);
if (cachedPrompt) {
  // Usar prompt em cache - 10x mais rápido!
}
```

### 4. Retry com Exponential Backoff

```typescript
// Automático em caso de erro
// Tentativa 1: aguarda 1s
// Tentativa 2: aguarda 2s
// Tentativa 3: aguarda 4s
// Resultado: Maior confiabilidade sem sobrecarregar a API
```

---

## Guia de Integração

### Passo 1: Instalar Dependências

```bash
npm install bcrypt ioredis
npm install --save-dev @types/bcrypt
```

### Passo 2: Configurar Variáveis de Ambiente

```bash
# .env
OPENAI_API_KEY=sk-...
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
```

### Passo 3: Inicializar Serviços

```typescript
// src/backend/index.ts
import SecurityService from './services/SecurityService';
import { createCacheService } from './services/CacheService';
import MessageProcessorService from './services/MessageProcessorService';

// Inicializar cache
const cache = createCacheService();

// Inicializar processador de mensagens
const messageProcessor = new MessageProcessorService(cache);

export { messageProcessor, cache };
```

### Passo 4: Usar no Router

```typescript
// src/backend/routers/messageRouter.ts
import { messageProcessor } from '../index';

export const messageRouter = router({
  send: protectedProcedure
    .input(z.object({
      agentId: z.number(),
      messageText: z.string(),
      contactPhone: z.string(),
      contactName: z.string(),
    }))
    .mutation(async ({ input, ctx }) => {
      const result = await messageProcessor.processMessage({
        userId: ctx.user.id,
        agentId: input.agentId,
        messageText: input.messageText,
        contactPhone: input.contactPhone,
        contactName: input.contactName,
        ipAddress: ctx.req.ip,
      });

      return result;
    }),
});
```

### Passo 5: Atualizar Schema do Banco

```typescript
// src/backend/db/schema.ts
export const users = sqliteTable('users', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  name: text('name').notNull(),
  email: text('email').notNull().unique(),
  password: text('password').notNull(), // ✅ Hash, não texto plano
  emailVerified: integer('emailVerified', { mode: 'boolean' }).default(false),
  emailVerificationToken: text('emailVerificationToken'),
  emailVerificationTokenExpires: integer('emailVerificationTokenExpires', { mode: 'timestamp' }),
  credits: integer('credits').default(100),
  referrerId: integer('referrerId'),
  createdAt: integer('createdAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
});

export const llmCallLogs = sqliteTable('llmCallLogs', {
  id: text('id').primaryKey(),
  userId: integer('userId').notNull(),
  agentId: integer('agentId').notNull(),
  model: text('model').notNull(),
  duration: integer('duration').notNull(),
  tokensUsed: integer('tokensUsed').notNull(),
  creditsUsed: real('creditsUsed').notNull(),
  status: text('status').notNull(),
  responseQuality: text('responseQuality'),
  createdAt: integer('createdAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
});

export const messageSources = sqliteTable('messageSources', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  messageId: integer('messageId').notNull(),
  type: text('type').notNull(),
  title: text('title').notNull(),
  excerpt: text('excerpt'),
  relevanceScore: integer('relevanceScore').notNull(),
  usedInResponse: integer('usedInResponse', { mode: 'boolean' }).notNull(),
  createdAt: integer('createdAt', { mode: 'timestamp' }).default(sql`CURRENT_TIMESTAMP`),
});
```

---

## Checklist de Implementação

### Fase 1: Segurança (1 Semana)

- [ ] Implementar SecurityService
- [ ] Atualizar authRouter com hashing de senhas
- [ ] Implementar rate limiting middleware
- [ ] Adicionar verificação de email
- [ ] Remover senhas de metadados do Mercado Pago
- [ ] Testes de segurança

### Fase 2: Transparência (2 Semanas)

- [ ] Implementar AICallLogger
- [ ] Criar tabelas de logging no banco
- [ ] Implementar rastreamento de sources
- [ ] Criar endpoints de transparência
- [ ] Criar dashboard de custos
- [ ] Testes de logging

### Fase 3: Eficiência (2 Semanas)

- [ ] Implementar EmbeddingSearchService
- [ ] Gerar embeddings para treinamentos existentes
- [ ] Implementar OptimizedPromptBuilder
- [ ] Implementar CacheService com Redis
- [ ] Refatorar MessageProcessorService
- [ ] Testes de performance

### Fase 4: Integração (1 Semana)

- [ ] Integrar todos os serviços
- [ ] Atualizar routers
- [ ] Testes de integração
- [ ] Documentação
- [ ] Deploy em staging

### Fase 5: Validação (1 Semana)

- [ ] Testes em produção
- [ ] Monitoramento
- [ ] Ajustes finais
- [ ] Deploy em produção

---

## Próximos Passos

1. **Implementar WebSocket** para status em tempo real
2. **Adicionar feedback loop** para melhoria contínua
3. **Implementar multi-channel** (Telegram, Web)
4. **Adicionar fine-tuning** de modelos
5. **Criar integração com CRM**

---

## Suporte

Para dúvidas ou problemas, consulte:
- Documentação do tRPC: https://trpc.io
- Documentação do Drizzle: https://orm.drizzle.team
- Documentação do bcrypt: https://github.com/kelektiv/node.bcrypt.js
- Documentação do Redis: https://redis.io

---

**Versão**: 1.0.0
**Data**: 10 de Janeiro de 2026
**Autor**: Manus AI
