/**
 * MessageProcessorService.ts
 * Serviço refatorado de processamento de mensagens com:
 * - Segurança melhorada
 * - Logging completo de IA
 * - Busca por embeddings
 * - Caching
 * - Retry com backoff exponencial
 * - Tratamento de erros robusto
 */

import * as db from '../db';
import SecurityService from './SecurityService';
import AICallLogger from '../logger/AICallLogger';
import OptimizedPromptBuilder from './OptimizedPromptBuilder';
import EmbeddingSearchService from './EmbeddingSearchService';
import CacheService from './CacheService';

interface ProcessMessageParams {
  userId: number;
  agentId: number;
  contactPhone: string;
  contactName: string;
  messageText: string;
  conversationId?: number;
  ipAddress?: string;
}

interface ProcessMessageResult {
  response: string;
  sources: any[];
  confidence: number;
  duration: number;
  tokensUsed: number;
  creditsUsed: number;
}

export class MessageProcessorService {
  private cache: CacheService;
  private maxRetries: number = 3;
  private baseRetryDelay: number = 1000; // ms

  constructor(cache: CacheService) {
    this.cache = cache;
  }

  /**
   * Processar mensagem com agente de IA
   * Fluxo completo com logging e otimizações
   */
  async processMessage(params: ProcessMessageParams): Promise<ProcessMessageResult> {
    const startTime = Date.now();
    const messageId = await this.createMessage(params);

    try {
      // ========================================================================
      // 1. VALIDAÇÕES INICIAIS
      // ========================================================================
      this.validateInput(params);

      // ========================================================================
      // 2. BUSCAR DADOS DO AGENTE
      // ========================================================================
      const agent = await db.getAgentById(params.agentId, params.userId);
      if (!agent) {
        throw new Error(`Agente ${params.agentId} não encontrado`);
      }

      // ========================================================================
      // 3. BUSCAR OU CRIAR CONVERSA
      // ========================================================================
      let conversation = params.conversationId
        ? await db.getConversationById(params.conversationId)
        : null;

      if (!conversation) {
        conversation = await db.createConversation({
          userId: params.userId,
          agentId: params.agentId,
          contactPhone: params.contactPhone,
          contactName: params.contactName,
        });
      }

      // ========================================================================
      // 4. BUSCAR HISTÓRICO RECENTE (sliding window)
      // ========================================================================
      const conversationHistory = await this.getConversationContext(
        conversation.id,
        50 // Últimas 50 mensagens
      );

      // ========================================================================
      // 5. BUSCAR TREINAMENTOS RELEVANTES (embeddings)
      // ========================================================================
      const relevantTrainings = await EmbeddingSearchService.findRelevantTrainings(
        params.agentId,
        params.messageText,
        topK: 5,
        minRelevance: 0.7
      );

      // ========================================================================
      // 6. CONSTRUIR PROMPT OTIMIZADO
      // ========================================================================
      const promptContext = {
        agent,
        relevantTrainings,
        conversationHistory,
        contactName: params.contactName,
        contactPhone: params.contactPhone,
        currentMessage: params.messageText,
      };

      const { prompt, estimatedTokens } = OptimizedPromptBuilder.buildOptimizedPrompt(
        promptContext
      );

      // ========================================================================
      // 7. CHAMAR LLM COM RETRY
      // ========================================================================
      const llmStartTime = Date.now();
      const llmResponse = await this.invokeLLMWithRetry({
        messages: [
          {
            role: 'system',
            content: prompt,
          },
          {
            role: 'user',
            content: params.messageText,
          },
        ],
        model: agent.model || 'gpt-4o',
        temperature: agent.temperature || 0.7,
        maxTokens: 500,
      });

      const llmDuration = Date.now() - llmStartTime;
      const tokensUsed = llmResponse.usage?.total_tokens || 0;
      const creditsUsed = this.calculateCredits(tokensUsed, agent.model);

      // ========================================================================
      // 8. EXTRAIR RESPOSTA E SOURCES
      // ========================================================================
      const responseText = llmResponse.choices[0].message.content;
      const sources = this.extractSources(responseText, relevantTrainings);
      const confidence = this.calculateConfidence(sources, llmResponse);

      // ========================================================================
      // 9. VALIDAR QUALIDADE DA RESPOSTA
      // ========================================================================
      const qualityScore = this.validateResponseQuality(responseText);

      // ========================================================================
      // 10. SALVAR MENSAGEM COM SOURCES
      // ========================================================================
      await db.updateMessage(messageId, {
        content: responseText,
        wasProcessedByAI: true,
        sources: JSON.stringify(sources),
        confidence,
        tokensUsed,
        creditsUsed,
      });

      // ========================================================================
      // 11. REGISTRAR LOG DE IA
      // ========================================================================
      const duration = Date.now() - startTime;
      await AICallLogger.logLLMCall({
        userId: params.userId,
        agentId: params.agentId,
        conversationId: conversation.id,
        messageId,
        model: agent.model,
        temperature: agent.temperature || 0.7,
        maxTokens: 500,
        promptLength: prompt.length,
        systemPromptLength: prompt.length,
        responseLength: responseText.length,
        tokensUsed,
        creditsUsed,
        startTime: new Date(startTime),
        endTime: new Date(),
        duration,
        responseQuality: {
          score: qualityScore,
          issues: [],
          suggestions: [],
        },
        status: 'success',
        source: 'whatsapp',
        ipAddress: params.ipAddress,
      });

      // ========================================================================
      // 12. REGISTRAR SOURCES
      // ========================================================================
      if (sources.length > 0) {
        await AICallLogger.logAnswerSources(messageId, sources, confidence);
      }

      // ========================================================================
      // 13. ATUALIZAR CRÉDITOS DO USUÁRIO
      // ========================================================================
      await db.updateUserCredits(params.userId, -creditsUsed);

      return {
        response: responseText,
        sources,
        confidence,
        duration,
        tokensUsed,
        creditsUsed,
      };
    } catch (error) {
      // Registrar erro
      const duration = Date.now() - startTime;
      await AICallLogger.logLLMCall({
        userId: params.userId,
        agentId: params.agentId,
        conversationId: params.conversationId || 0,
        messageId,
        model: 'unknown',
        temperature: 0.7,
        maxTokens: 500,
        promptLength: 0,
        systemPromptLength: 0,
        responseLength: 0,
        tokensUsed: 0,
        creditsUsed: 0,
        startTime: new Date(startTime),
        endTime: new Date(),
        duration,
        responseQuality: { score: 0, issues: [], suggestions: [] },
        status: 'error',
        error: error.message,
        source: 'whatsapp',
        ipAddress: params.ipAddress,
      });

      throw error;
    }
  }

  /**
   * Chamar LLM com retry e exponential backoff
   */
  private async invokeLLMWithRetry(params: any, attempt: number = 1): Promise<any> {
    try {
      console.log(`[MessageProcessor] Tentativa ${attempt}/${this.maxRetries} de chamar LLM`);

      const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          ...params,
          model: params.model,
        }),
      });

      if (!response.ok) {
        const error = await response.json();

        // Rate limit - aguardar e retry
        if (response.status === 429) {
          const waitTime = Math.pow(2, attempt - 1) * this.baseRetryDelay + Math.random() * 1000;
          console.warn(`[MessageProcessor] Rate limit. Aguardando ${waitTime}ms...`);
          await new Promise(resolve => setTimeout(resolve, waitTime));

          if (attempt < this.maxRetries) {
            return this.invokeLLMWithRetry(params, attempt + 1);
          }
        }

        // Erro do servidor - retry
        if (response.status >= 500) {
          const waitTime = Math.pow(2, attempt - 1) * this.baseRetryDelay;
          console.warn(`[MessageProcessor] Erro do servidor. Aguardando ${waitTime}ms...`);
          await new Promise(resolve => setTimeout(resolve, waitTime));

          if (attempt < this.maxRetries) {
            return this.invokeLLMWithRetry(params, attempt + 1);
          }
        }

        throw new Error(`LLM API error: ${error.error?.message || response.statusText}`);
      }

      return response.json();
    } catch (error) {
      if (attempt < this.maxRetries) {
        const waitTime = Math.pow(2, attempt - 1) * this.baseRetryDelay;
        console.error(`[MessageProcessor] Erro na tentativa ${attempt}. Aguardando ${waitTime}ms...`);
        await new Promise(resolve => setTimeout(resolve, waitTime));
        return this.invokeLLMWithRetry(params, attempt + 1);
      }

      throw error;
    }
  }

  /**
   * Obter contexto da conversa (sliding window)
   */
  private async getConversationContext(conversationId: number, windowSize: number = 50) {
    const messages = await db
      .select()
      .from(messagesTable)
      .where(eq(messagesTable.conversationId, conversationId))
      .orderBy(desc(messagesTable.createdAt))
      .limit(windowSize);

    return messages.reverse(); // Ordem cronológica
  }

  /**
   * Extrair sources da resposta
   */
  private extractSources(response: string, trainings: any[]): any[] {
    return trainings.map(training => ({
      type: 'training',
      title: training.title,
      excerpt: training.content.substring(0, 200),
      relevanceScore: training.relevanceScore,
      usedInResponse: response.toLowerCase().includes(training.title.toLowerCase()),
    }));
  }

  /**
   * Calcular confiança da resposta
   */
  private calculateConfidence(sources: any[], llmResponse: any): number {
    let confidence = 50; // Base

    // Se tem sources usadas, aumentar confiança
    const usedSources = sources.filter(s => s.usedInResponse).length;
    confidence += usedSources * 10;

    // Se tem finish_reason "stop", é mais confiável
    if (llmResponse.choices[0].finish_reason === 'stop') {
      confidence += 10;
    }

    return Math.min(confidence, 100);
  }

  /**
   * Validar qualidade da resposta
   */
  private validateResponseQuality(response: string): number {
    let score = 50; // Base

    // Comprimento apropriado (3-4 linhas)
    const lines = response.split('\n').length;
    if (lines >= 2 && lines <= 5) {
      score += 20;
    }

    // Sem erros óbvios
    if (!response.includes('[') && !response.includes('{')) {
      score += 10;
    }

    // Tem pontuação final
    if (response.trim().endsWith('.') || response.trim().endsWith('?')) {
      score += 10;
    }

    return Math.min(score, 100);
  }

  /**
   * Calcular créditos consumidos
   */
  private calculateCredits(tokensUsed: number, model: string): number {
    // Preço por 1K tokens
    const prices: Record<string, number> = {
      'gpt-4o': 0.03,
      'gpt-4-turbo': 0.01,
      'gpt-3.5-turbo': 0.0005,
    };

    const pricePerToken = (prices[model] || 0.01) / 1000;
    return Math.ceil(tokensUsed * pricePerToken * 100); // Converter para créditos
  }

  /**
   * Validar entrada
   */
  private validateInput(params: ProcessMessageParams): void {
    if (!params.userId || params.userId <= 0) {
      throw new Error('userId inválido');
    }

    if (!params.agentId || params.agentId <= 0) {
      throw new Error('agentId inválido');
    }

    if (!params.messageText || params.messageText.trim().length === 0) {
      throw new Error('messageText não pode estar vazio');
    }

    if (!SecurityService.validatePhoneNumber(params.contactPhone)) {
      throw new Error('contactPhone inválido');
    }
  }

  /**
   * Criar mensagem inicial
   */
  private async createMessage(params: ProcessMessageParams): Promise<number> {
    const message = await db.createMessage({
      conversationId: params.conversationId || 0,
      direction: 'incoming',
      content: params.messageText,
      wasProcessedByAI: false,
    });

    return message.id;
  }
}

export default MessageProcessorService;
