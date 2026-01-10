# MELHORIAS EM TRANSPARÊNCIA, COMUNICAÇÃO E EFICIÊNCIA DAS IAs

## 1. TRANSPARÊNCIA - VISIBILIDADE COMPLETA DO PROCESSAMENTO

### 1.1 Logging Completo de LLM Calls

**Problema Atual**: Sem registro de qual prompt foi enviado, qual modelo foi usado, qual foi a resposta

**Solução Proposta**:
```typescript
// logger/llmLogger.ts
export interface LLMCallLog {
  id: string;
  userId: number;
  agentId: number;
  conversationId: number;
  messageId: number;
  
  // Input
  model: string;
  temperature: number;
  maxTokens: number;
  promptLength: number;
  systemPromptLength: number;
  
  // Output
  responseLength: number;
  tokensUsed: number;
  creditsUsed: number;
  
  // Timing
  startTime: Date;
  endTime: Date;
  duration: number; // ms
  
  // Quality
  responseQuality: {
    score: number;
    issues: string[];
    suggestions: string[];
  };
  
  // Status
  status: 'success' | 'error' | 'timeout';
  error?: string;
  
  // Metadata
  source: 'whatsapp' | 'api' | 'webhook';
  ipAddress: string;
  userAgent: string;
  
  createdAt: Date;
}

export async function logLLMCall(data: LLMCallLog) {
  // Salvar em database
  await db.insert(llmCallLogs).values(data);
  
  // Enviar para analytics
  await analytics.track('llm_call', {
    userId: data.userId,
    agentId: data.agentId,
    model: data.model,
    duration: data.duration,
    tokensUsed: data.tokensUsed,
    status: data.status,
  });
  
  // Alertar se problema
  if (data.status === 'error' || data.duration > 10000) {
    await alerts.notify({
      level: 'warning',
      message: `LLM call slow or failed: ${data.agentId}`,
      data,
    });
  }
}
```

### 1.2 Rastreamento de Fontes (Answer Sources)

**Problema Atual**: Usuário não sabe de onde a IA buscou a resposta

**Solução Proposta**:
```typescript
// types/answerSource.ts
export interface AnswerSource {
  type: 'training' | 'knowledge_base' | 'web' | 'api' | 'generated';
  title: string;
  url?: string;
  excerpt: string;
  relevanceScore: number; // 0-100
  usedInResponse: boolean;
}

export interface MessageWithSources {
  id: number;
  content: string;
  sources: AnswerSource[];
  confidence: number; // 0-100
  generatedAt: Date;
}

// messageProcessor.ts - modificado
export async function processMessageWithAgent(params: {
  userId: number;
  agentId: number;
  contactPhone: string;
  contactName: string;
  messageText: string;
  conversationId?: number;
}) {
  // ... código anterior ...
  
  // Buscar relevância de cada training
  const relevantTrainings = await findRelevantTrainings(
    agentId,
    messageText,
    topK: 5
  );
  
  const sources: AnswerSource[] = relevantTrainings.map(t => ({
    type: 'training',
    title: t.title,
    excerpt: t.content.substring(0, 200),
    relevanceScore: t.relevanceScore,
    usedInResponse: false,
  }));
  
  // Chamar LLM
  const llmResponse = await invokeLLM({
    messages: llmMessages,
    model: agent.model,
  });
  
  // Analisar quais fontes foram usadas
  const usedSources = analyzeSourceUsage(
    llmResponse.choices[0].message.content,
    relevantTrainings
  );
  
  sources.forEach(s => {
    if (usedSources.includes(s.title)) {
      s.usedInResponse = true;
    }
  });
  
  // Salvar mensagem com sources
  await db.createMessage({
    conversationId: conversation.id,
    direction: 'outgoing',
    content: finalResponse,
    wasProcessedByAI: true,
    sources: JSON.stringify(sources),
    confidence: calculateConfidence(sources, llmResponse),
  });
  
  return {
    response: finalResponse,
    sources,
    confidence: calculateConfidence(sources, llmResponse),
  };
}
```

### 1.3 Dashboard de Transparência para Usuários

**Componente React**:
```typescript
// components/TransparencyDashboard.tsx
export function TransparencyDashboard({ agentId }: { agentId: number }) {
  const { data: logs } = trpc.transparency.getLLMCalls.useQuery({ agentId });
  const { data: costBreakdown } = trpc.transparency.getCostBreakdown.useQuery({ agentId });
  
  return (
    <div className="space-y-6">
      {/* LLM Calls Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Histórico de Chamadas de IA</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {logs?.map(log => (
              <div key={log.id} className="border rounded p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-semibold">{log.model}</p>
                    <p className="text-sm text-gray-500">
                      {log.duration}ms | {log.tokensUsed} tokens | {log.creditsUsed} créditos
                    </p>
                  </div>
                  <Badge variant={log.status === 'success' ? 'default' : 'destructive'}>
                    {log.status}
                  </Badge>
                </div>
                
                {/* Expandable Details */}
                <details className="mt-2">
                  <summary className="cursor-pointer text-sm text-blue-600">
                    Ver detalhes
                  </summary>
                  <div className="mt-2 space-y-2 text-sm">
                    <p><strong>Prompt:</strong> {log.promptLength} chars</p>
                    <p><strong>Resposta:</strong> {log.responseLength} chars</p>
                    <p><strong>Qualidade:</strong> {log.responseQuality.score}/100</p>
                    {log.responseQuality.issues.length > 0 && (
                      <div>
                        <strong>Problemas:</strong>
                        <ul className="list-disc ml-4">
                          {log.responseQuality.issues.map(issue => (
                            <li key={issue}>{issue}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </details>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      
      {/* Cost Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Análise de Custos</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-gray-500">Total de Créditos Usados</p>
              <p className="text-2xl font-bold">{costBreakdown?.totalCredits}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Custo Médio por Mensagem</p>
              <p className="text-2xl font-bold">{costBreakdown?.avgCostPerMessage}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Economia vs Humano</p>
              <p className="text-2xl font-bold text-green-600">
                {costBreakdown?.savingsVsHuman}%
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

---

## 2. COMUNICAÇÃO - MELHOR FEEDBACK E CONTROLE

### 2.1 Real-time Status Updates via WebSocket

**Problema Atual**: Usuário não sabe se agente está processando, se há erro, etc

**Solução Proposta**:
```typescript
// services/messageStatusService.ts
export class MessageStatusService {
  private io: Server;
  
  async processMessage(params: {
    userId: number;
    agentId: number;
    messageId: number;
    conversationId: number;
  }) {
    const { userId, agentId, messageId, conversationId } = params;
    
    // Notificar que começou a processar
    this.io.to(`user:${userId}`).emit('message:processing', {
      messageId,
      status: 'analyzing',
      timestamp: new Date(),
    });
    
    try {
      // Buscar agente
      const agent = await db.getAgentById(agentId, userId);
      this.io.to(`user:${userId}`).emit('message:processing', {
        messageId,
        status: 'loading_context',
        timestamp: new Date(),
      });
      
      // Buscar contexto
      const trainings = await db.getTrainingsByAgentId(agentId);
      this.io.to(`user:${userId}`).emit('message:processing', {
        messageId,
        status: 'building_prompt',
        timestamp: new Date(),
      });
      
      // Construir prompt
      const prompt = buildIntelligentPrompt({ /* ... */ });
      this.io.to(`user:${userId}`).emit('message:processing', {
        messageId,
        status: 'calling_llm',
        model: agent.model,
        timestamp: new Date(),
      });
      
      // Chamar LLM
      const startTime = Date.now();
      const response = await invokeLLM({ /* ... */ });
      const duration = Date.now() - startTime;
      
      this.io.to(`user:${userId}`).emit('message:processing', {
        messageId,
        status: 'validating',
        duration,
        tokensUsed: response.usage.total_tokens,
        timestamp: new Date(),
      });
      
      // Validar qualidade
      const quality = validateResponseQuality(response.choices[0].message.content);
      this.io.to(`user:${userId}`).emit('message:processing', {
        messageId,
        status: 'complete',
        quality: quality.score,
        duration,
        timestamp: new Date(),
      });
      
      return response;
    } catch (error) {
      this.io.to(`user:${userId}`).emit('message:processing', {
        messageId,
        status: 'error',
        error: error.message,
        timestamp: new Date(),
      });
      throw error;
    }
  }
}

// Frontend - React Component
export function MessageProcessing({ messageId }: { messageId: number }) {
  const [status, setStatus] = useState<string>('analyzing');
  const [details, setDetails] = useState<any>(null);
  
  useEffect(() => {
    const socket = io();
    socket.on('message:processing', (data) => {
      if (data.messageId === messageId) {
        setStatus(data.status);
        setDetails(data);
      }
    });
    
    return () => socket.disconnect();
  }, [messageId]);
  
  const statusMessages = {
    analyzing: '🔍 Analisando mensagem...',
    loading_context: '📚 Carregando contexto...',
    building_prompt: '🔨 Construindo prompt...',
    calling_llm: `🤖 Chamando ${details?.model}...`,
    validating: '✅ Validando resposta...',
    complete: '✨ Completo!',
    error: '❌ Erro ao processar',
  };
  
  return (
    <div className="flex items-center gap-2">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span>{statusMessages[status] || status}</span>
      {details?.duration && (
        <span className="text-sm text-gray-500">({details.duration}ms)</span>
      )}
    </div>
  );
}
```

### 2.2 Feedback Loop - Usuário Avalia Resposta

**Problema Atual**: Sem feedback do usuário, IA não melhora

**Solução Proposta**:
```typescript
// types/feedback.ts
export interface MessageFeedback {
  messageId: number;
  userId: number;
  rating: 1 | 2 | 3 | 4 | 5; // 1 = ruim, 5 = excelente
  feedback: string; // Comentário do usuário
  issues: string[]; // Tags de problemas
  suggestions: string[]; // Sugestões de melhoria
  createdAt: Date;
}

// routers/feedback.ts
export const feedbackRouter = router({
  submitFeedback: protectedProcedure
    .input(
      z.object({
        messageId: z.number(),
        rating: z.number().min(1).max(5),
        feedback: z.string().optional(),
        issues: z.array(z.string()).optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      // Salvar feedback
      const feedback = await db.createFeedback({
        messageId: input.messageId,
        userId: ctx.user.id,
        rating: input.rating,
        feedback: input.feedback,
        issues: input.issues,
      });
      
      // Se rating baixo, notificar usuário
      if (input.rating <= 2) {
        await sendAlert({
          userId: ctx.user.id,
          message: 'Detectamos uma resposta com baixa qualidade. Estamos analisando.',
          type: 'info',
        });
      }
      
      // Usar feedback para melhorar prompt
      if (input.rating >= 4) {
        // Adicionar exemplo positivo ao prompt
        await db.addPromptExample({
          agentId: feedback.agentId,
          type: 'positive',
          userMessage: feedback.userMessage,
          aiResponse: feedback.aiResponse,
          feedback: input.feedback,
        });
      }
      
      return { success: true };
    }),
});

// Frontend Component
export function FeedbackWidget({ messageId, agentId }: { messageId: number; agentId: number }) {
  const [rating, setRating] = useState<number>(0);
  const [showDetails, setShowDetails] = useState(false);
  const feedbackMutation = trpc.feedback.submitFeedback.useMutation();
  
  const handleSubmit = async (feedback: string) => {
    await feedbackMutation.mutateAsync({
      messageId,
      rating,
      feedback,
    });
    toast.success('Obrigado pelo feedback!');
  };
  
  return (
    <div className="flex items-center gap-2 p-2 bg-gray-50 rounded">
      <span className="text-sm">Útil?</span>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map(i => (
          <button
            key={i}
            onClick={() => setRating(i)}
            className={`text-xl ${i <= rating ? 'opacity-100' : 'opacity-30'}`}
          >
            {i <= 2 ? '👎' : i <= 3 ? '😐' : '👍'}
          </button>
        ))}
      </div>
      {rating > 0 && (
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-sm text-blue-600 hover:underline"
        >
          Comentar
        </button>
      )}
      
      {showDetails && (
        <textarea
          placeholder="Nos ajude a melhorar..."
          className="text-sm p-2 border rounded"
          onBlur={(e) => handleSubmit(e.target.value)}
        />
      )}
    </div>
  );
}
```

### 2.3 Sugestões de Resposta (Message Suggestions)

**Problema Atual**: Usuário não sabe como melhorar a conversa

**Solução Proposta**:
```typescript
// services/messageSuggestions.ts
export async function generateMessageSuggestions(params: {
  conversationId: number;
  lastUserMessage: string;
  agentId: number;
  context: string;
}): Promise<string[]> {
  const { conversationId, lastUserMessage, agentId, context } = params;
  
  // Usar LLM para gerar sugestões
  const response = await invokeLLM({
    messages: [
      {
        role: 'system',
        content: `Você é um assistente que gera sugestões de próximas perguntas para melhorar a conversa.
        
Contexto do agente:
${context}

Última mensagem do usuário: "${lastUserMessage}"

Gere 3 sugestões de próximas perguntas que o usuário poderia fazer para:
1. Aprofundar o tópico
2. Esclarecer dúvidas
3. Explorar alternativas

Retorne como JSON array: ["sugestão1", "sugestão2", "sugestão3"]`,
      },
    ],
    model: 'gpt-3.5-turbo',
  });
  
  const suggestions = JSON.parse(response.choices[0].message.content);
  
  // Salvar para análise
  await db.createMessageSuggestions({
    conversationId,
    suggestions,
  });
  
  return suggestions;
}

// Frontend Component
export function MessageSuggestions({ conversationId }: { conversationId: number }) {
  const { data: suggestions } = trpc.messages.getSuggestions.useQuery({ conversationId });
  const [, setLocation] = useLocation();
  
  if (!suggestions?.length) return null;
  
  return (
    <div className="bg-blue-50 border border-blue-200 rounded p-3 space-y-2">
      <p className="text-sm font-semibold text-blue-900">Sugestões de próximas perguntas:</p>
      <div className="space-y-1">
        {suggestions.map((suggestion, idx) => (
          <button
            key={idx}
            onClick={() => {
              // Enviar sugestão como mensagem
              const input = document.querySelector('input[type="text"]') as HTMLInputElement;
              if (input) {
                input.value = suggestion;
                input.focus();
              }
            }}
            className="block w-full text-left text-sm p-2 hover:bg-blue-100 rounded cursor-pointer"
          >
            💡 {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}
```

---

## 3. EFICIÊNCIA DAS IAs - MELHOR QUALIDADE E VELOCIDADE

### 3.1 Prompt Otimizado com Estrutura Consistente

**Problema Atual**: Prompt muito longo, desorganizado, sem exemplos

**Solução Proposta**:
```typescript
// services/optimizedPromptBuilder.ts
export function buildOptimizedPrompt(context: PromptContext): string {
  const { agent, trainings, messages, contactName, currentMessage } = context;
  
  // Usar formato estruturado (XML)
  let prompt = `<?xml version="1.0" encoding="UTF-8"?>
<agent>
  <identity>
    <name>${agent.name}</name>
    <role>${getPurposeDescription(agent.purpose)}</role>
    <style>${getStyleDescription(agent.communicationStyle)}</style>
    <description>${agent.description || ''}</description>
  </identity>
  
  <business>
    <product>${agent.productName || 'N/A'}</product>
    <description>${agent.productDescription || ''}</description>
    <website>${agent.websiteUrl || ''}</website>
  </business>
  
  <knowledge>
    <count>${trainings.length}</count>
    ${trainings.slice(0, 5).map(t => `
    <document>
      <title>${t.title}</title>
      <content>${t.content.substring(0, 500)}</content>
    </document>
    `).join('')}
  </knowledge>
  
  <conversation>
    <client>${contactName}</client>
    <history>
      ${messages.slice(-10).map(m => `
      <message>
        <sender>${m.direction === 'incoming' ? 'client' : 'agent'}</sender>
        <text>${m.content}</text>
      </message>
      `).join('')}
    </history>
    <current_message>${currentMessage}</current_message>
  </conversation>
  
  <instructions>
    <constraint>Máximo 4 linhas</constraint>
    <tone>${agent.communicationStyle}</tone>
    <focus>Ser útil, conciso e profissional</focus>
    <fallback>Se não sabe, diga "Deixe-me conectar você com um especialista"</fallback>
  </instructions>
  
  <examples>
    <example>
      <user>Qual é o preço?</user>
      <agent>Nossos planos começam em R$ 99/mês. Qual seria melhor para você?</agent>
    </example>
    <example>
      <user>Como funciona?</user>
      <agent>É simples: 1) Crie um agente, 2) Treine com seus dados, 3) Integre ao WhatsApp. Quer começar?</agent>
    </example>
  </examples>
  
  <task>
    Responda à mensagem do cliente seguindo EXATAMENTE as instruções acima.
    Use a base de conhecimento quando relevante.
    Mantenha o tom e estilo definidos.
  </task>
</agent>`;
  
  return prompt;
}
```

### 3.2 Sliding Window para Histórico

**Problema Atual**: Carregar todas as mensagens da conversa (1000+ linhas)

**Solução Proposta**:
```typescript
// services/conversationContext.ts
export async function getConversationContext(
  conversationId: number,
  windowSize: number = 50
): Promise<Message[]> {
  // Buscar apenas as últimas N mensagens
  const messages = await db.query(
    `SELECT * FROM messages 
     WHERE conversationId = ? 
     ORDER BY createdAt DESC 
     LIMIT ?`,
    [conversationId, windowSize]
  );
  
  // Se conversa é muito longa, incluir resumo do início
  const totalMessages = await db.query(
    `SELECT COUNT(*) as count FROM messages WHERE conversationId = ?`,
    [conversationId]
  );
  
  if (totalMessages[0].count > windowSize) {
    // Gerar resumo das mensagens antigas
    const oldMessages = await db.query(
      `SELECT * FROM messages 
       WHERE conversationId = ? 
       ORDER BY createdAt ASC 
       LIMIT 20`,
      [conversationId]
    );
    
    const summary = await generateConversationSummary(oldMessages);
    
    // Adicionar resumo como contexto
    messages.unshift({
      id: 0,
      conversationId,
      direction: 'system',
      content: `[RESUMO DAS MENSAGENS ANTERIORES]\n${summary}\n[FIM DO RESUMO]`,
      wasProcessedByAI: false,
      createdAt: new Date(),
    });
  }
  
  return messages.reverse(); // Ordem cronológica
}

async function generateConversationSummary(messages: Message[]): Promise<string> {
  const response = await invokeLLM({
    messages: [
      {
        role: 'system',
        content: 'Resuma brevemente o contexto dessa conversa em 2-3 linhas.',
      },
      {
        role: 'user',
        content: messages.map(m => `${m.direction}: ${m.content}`).join('\n'),
      },
    ],
    model: 'gpt-3.5-turbo',
  });
  
  return response.choices[0].message.content;
}
```

### 3.3 Embedding Search para Relevância

**Problema Atual**: Incluir toda base de conhecimento no prompt

**Solução Proposta**:
```typescript
// services/embeddingSearch.ts
import { OpenAIEmbeddings } from 'langchain/embeddings/openai';
import { PineconeStore } from 'langchain/vectorstores/pinecone';

export async function findRelevantTrainings(
  agentId: number,
  query: string,
  topK: number = 5
): Promise<Training[]> {
  // Gerar embedding da mensagem
  const embeddings = new OpenAIEmbeddings();
  const queryEmbedding = await embeddings.embedQuery(query);
  
  // Buscar no Pinecone
  const vectorStore = await PineconeStore.fromExistingIndex(embeddings, {
    pineconeIndex: `agent-${agentId}`,
  });
  
  const results = await vectorStore.similaritySearchWithScore(query, topK);
  
  // Converter para Training objects
  const trainings = await Promise.all(
    results.map(async ([doc, score]) => {
      const training = await db.getTrainingById(doc.metadata.trainingId);
      return {
        ...training,
        relevanceScore: score,
      };
    })
  );
  
  return trainings.sort((a, b) => b.relevanceScore - a.relevanceScore);
}

// messageProcessor.ts - modificado
export async function processMessageWithAgent(params: {
  userId: number;
  agentId: number;
  contactPhone: string;
  contactName: string;
  messageText: string;
}) {
  // ... código anterior ...
  
  // Buscar apenas treinamentos relevantes
  const relevantTrainings = await findRelevantTrainings(
    agentId,
    messageText,
    topK: 5 // Apenas top 5
  );
  
  // Filtrar por relevância mínima
  const filteredTrainings = relevantTrainings.filter(t => t.relevanceScore > 0.7);
  
  // Construir prompt com apenas treinamentos relevantes
  const systemPrompt = buildOptimizedPrompt({
    agent,
    trainings: filteredTrainings, // Apenas relevantes
    messages: conversationContext,
    contactName,
    contactPhone,
    currentMessage: messageText,
  });
  
  // ... resto do código ...
}
```

### 3.4 Caching de Prompts

**Problema Atual**: Reconstruir prompt a cada mensagem

**Solução Proposta**:
```typescript
// services/promptCache.ts
import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL);

export async function getCachedPrompt(
  agentId: number,
  trainingIds: string[]
): Promise<string | null> {
  const cacheKey = `prompt:${agentId}:${trainingIds.sort().join(',')}`;
  return redis.get(cacheKey);
}

export async function cachePrompt(
  agentId: number,
  trainingIds: string[],
  prompt: string,
  ttl: number = 3600 // 1 hora
): Promise<void> {
  const cacheKey = `prompt:${agentId}:${trainingIds.sort().join(',')}`;
  await redis.setex(cacheKey, ttl, prompt);
}

export async function invalidateAgentCache(agentId: number): Promise<void> {
  const keys = await redis.keys(`prompt:${agentId}:*`);
  if (keys.length > 0) {
    await redis.del(...keys);
  }
}

// messageProcessor.ts - modificado
export async function processMessageWithAgent(params: {
  userId: number;
  agentId: number;
  contactPhone: string;
  contactName: string;
  messageText: string;
}) {
  // ... código anterior ...
  
  const relevantTrainings = await findRelevantTrainings(agentId, messageText);
  const trainingIds = relevantTrainings.map(t => t.id.toString());
  
  // Tentar buscar do cache
  let systemPrompt = await getCachedPrompt(agentId, trainingIds);
  
  if (!systemPrompt) {
    // Construir novo prompt
    systemPrompt = buildOptimizedPrompt({
      agent,
      trainings: relevantTrainings,
      messages: conversationContext,
      contactName,
      contactPhone,
      currentMessage: messageText,
    });
    
    // Cachear para próximas vezes
    await cachePrompt(agentId, trainingIds, systemPrompt);
  }
  
  // ... resto do código ...
}
```

### 3.5 Retry com Exponential Backoff

**Problema Atual**: Se LLM falha, sem retry

**Solução Proposta**:
```typescript
// services/llmRetry.ts
export async function invokeLLMWithRetry(
  params: LLMParams,
  maxRetries: number = 3
): Promise<LLMResponse> {
  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      console.log(`[LLM] Tentativa ${attempt + 1}/${maxRetries}`);
      
      const response = await invokeLLM(params);
      
      // Sucesso
      console.log(`[LLM] Sucesso na tentativa ${attempt + 1}`);
      return response;
    } catch (error) {
      lastError = error;
      
      // Se for erro de rate limit, aguardar mais
      if (error.status === 429) {
        const waitTime = Math.pow(2, attempt) * 1000 + Math.random() * 1000;
        console.log(`[LLM] Rate limit. Aguardando ${waitTime}ms...`);
        await new Promise(resolve => setTimeout(resolve, waitTime));
      } else if (error.status >= 500) {
        // Erro do servidor, tentar novamente
        const waitTime = Math.pow(2, attempt) * 500;
        console.log(`[LLM] Erro do servidor. Aguardando ${waitTime}ms...`);
        await new Promise(resolve => setTimeout(resolve, waitTime));
      } else {
        // Erro do cliente, não fazer retry
        throw error;
      }
    }
  }
  
  throw new Error(`LLM failed after ${maxRetries} attempts: ${lastError?.message}`);
}
```

---

## 4. RESUMO DE MELHORIAS

| Área | Problema | Solução | Impacto |
|------|----------|---------|--------|
| **Transparência** | Sem logging de LLM calls | Logging completo com métricas | Visibilidade total |
| **Transparência** | Sem rastreamento de fontes | Answer sources | Confiança do usuário |
| **Comunicação** | Sem feedback em tempo real | WebSocket status updates | UX melhorada |
| **Comunicação** | Sem feedback do usuário | Rating + feedback loop | Melhoria contínua |
| **Comunicação** | Sem sugestões | Message suggestions | Engajamento |
| **Eficiência** | Prompt desorganizado | XML structured prompt | Respostas melhores |
| **Eficiência** | Histórico muito longo | Sliding window | Menos tokens |
| **Eficiência** | Sem busca relevante | Embedding search | Contexto melhor |
| **Eficiência** | Sem cache | Redis caching | Velocidade 10x |
| **Eficiência** | Sem retry | Exponential backoff | Confiabilidade |

---

## 5. IMPLEMENTAÇÃO RECOMENDADA

### Semana 1
- [ ] Logging de LLM calls
- [ ] Answer sources
- [ ] Feedback widget

### Semana 2-3
- [ ] WebSocket status updates
- [ ] Optimized prompt builder
- [ ] Embedding search

### Semana 4
- [ ] Sliding window
- [ ] Redis caching
- [ ] Retry logic

### Semana 5+
- [ ] Message suggestions
- [ ] Advanced analytics
- [ ] Fine-tuning loop
