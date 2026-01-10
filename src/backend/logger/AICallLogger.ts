/**
 * AICallLogger.ts
 * Sistema completo de logging para chamadas de IA
 * Registra: prompt, resposta, tokens, custo, duração, qualidade
 */

import * as db from '../db';

export interface LLMCallLog {
  id?: string;
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
  source: 'whatsapp' | 'api' | 'webhook' | 'test';
  ipAddress?: string;
  userAgent?: string;

  createdAt: Date;
}

export interface AnswerSource {
  type: 'training' | 'knowledge_base' | 'web' | 'api' | 'generated';
  title: string;
  url?: string;
  excerpt: string;
  relevanceScore: number; // 0-100
  usedInResponse: boolean;
}

export class AICallLogger {
  /**
   * Registrar chamada de IA completa
   */
  static async logLLMCall(logData: LLMCallLog): Promise<void> {
    try {
      // 1. Salvar no banco de dados para auditoria
      await db.insert(llmCallLogs).values({
        ...logData,
        createdAt: new Date(),
      });

      // 2. Enviar para analytics (PostHog, Mixpanel, etc)
      await this.sendToAnalytics({
        userId: logData.userId,
        agentId: logData.agentId,
        model: logData.model,
        duration: logData.duration,
        tokensUsed: logData.tokensUsed,
        creditsUsed: logData.creditsUsed,
        status: logData.status,
        qualityScore: logData.responseQuality.score,
      });

      // 3. Alertar se problema crítico
      if (logData.status === 'error' || logData.duration > 15000) {
        await this.alertInternal({
          level: logData.status === 'error' ? 'error' : 'warning',
          message: `LLM Call Alert | Agent: ${logData.agentId} | Status: ${logData.status} | Duration: ${logData.duration}ms`,
          data: logData,
        });
      }

      // 4. Log em arquivo para debugging
      console.log(
        `[AICallLogger] LLM Call Logged | Agent: ${logData.agentId} | Model: ${logData.model} | Duration: ${logData.duration}ms | Status: ${logData.status}`
      );
    } catch (error) {
      console.error('[AICallLogger] Erro ao registrar chamada de IA:', error);
      // Não lançar erro para não interromper o fluxo
    }
  }

  /**
   * Registrar sources (fontes) usadas na resposta
   */
  static async logAnswerSources(
    messageId: number,
    sources: AnswerSource[],
    confidence: number
  ): Promise<void> {
    try {
      await db.insert(messageSources).values(
        sources.map(source => ({
          messageId,
          type: source.type,
          title: source.title,
          url: source.url,
          excerpt: source.excerpt,
          relevanceScore: source.relevanceScore,
          usedInResponse: source.usedInResponse,
          confidence,
          createdAt: new Date(),
        }))
      );

      console.log(
        `[AICallLogger] Sources logged for message ${messageId} | Count: ${sources.length} | Confidence: ${confidence}%`
      );
    } catch (error) {
      console.error('[AICallLogger] Erro ao registrar sources:', error);
    }
  }

  /**
   * Registrar feedback do usuário
   */
  static async logUserFeedback(
    messageId: number,
    userId: number,
    rating: number,
    feedback?: string,
    issues?: string[]
  ): Promise<void> {
    try {
      await db.insert(messageFeedback).values({
        messageId,
        userId,
        rating,
        feedback,
        issues: JSON.stringify(issues || []),
        createdAt: new Date(),
      });

      console.log(
        `[AICallLogger] Feedback logged for message ${messageId} | Rating: ${rating}/5`
      );

      // Se rating baixo, investigar
      if (rating <= 2) {
        await this.alertInternal({
          level: 'warning',
          message: `Low quality feedback detected | Message: ${messageId} | Rating: ${rating}/5`,
          data: { messageId, userId, rating, feedback, issues },
        });
      }
    } catch (error) {
      console.error('[AICallLogger] Erro ao registrar feedback:', error);
    }
  }

  /**
   * Obter histórico de chamadas de IA para um agente
   */
  static async getAgentCallHistory(
    agentId: number,
    limit: number = 100,
    offset: number = 0
  ): Promise<LLMCallLog[]> {
    try {
      const logs = await db
        .select()
        .from(llmCallLogs)
        .where(eq(llmCallLogs.agentId, agentId))
        .orderBy(desc(llmCallLogs.createdAt))
        .limit(limit)
        .offset(offset);

      return logs;
    } catch (error) {
      console.error('[AICallLogger] Erro ao buscar histórico:', error);
      return [];
    }
  }

  /**
   * Obter estatísticas de custo para um agente
   */
  static async getAgentCostStats(agentId: number): Promise<{
    totalCreditsUsed: number;
    avgCostPerMessage: number;
    totalMessages: number;
    avgQualityScore: number;
    errorRate: number;
  }> {
    try {
      const logs = await db
        .select()
        .from(llmCallLogs)
        .where(eq(llmCallLogs.agentId, agentId));

      if (logs.length === 0) {
        return {
          totalCreditsUsed: 0,
          avgCostPerMessage: 0,
          totalMessages: 0,
          avgQualityScore: 0,
          errorRate: 0,
        };
      }

      const totalCredits = logs.reduce((sum, log) => sum + log.creditsUsed, 0);
      const totalMessages = logs.length;
      const avgCost = totalCredits / totalMessages;
      const avgQuality =
        logs.reduce((sum, log) => sum + log.responseQuality.score, 0) /
        totalMessages;
      const errorCount = logs.filter(log => log.status === 'error').length;
      const errorRate = (errorCount / totalMessages) * 100;

      return {
        totalCreditsUsed: totalCredits,
        avgCostPerMessage: Math.round(avgCost * 100) / 100,
        totalMessages,
        avgQualityScore: Math.round(avgQuality),
        errorRate: Math.round(errorRate * 100) / 100,
      };
    } catch (error) {
      console.error('[AICallLogger] Erro ao calcular estatísticas:', error);
      return {
        totalCreditsUsed: 0,
        avgCostPerMessage: 0,
        totalMessages: 0,
        avgQualityScore: 0,
        errorRate: 0,
      };
    }
  }

  /**
   * Enviar dados para plataforma de analytics
   */
  private static async sendToAnalytics(data: any): Promise<void> {
    try {
      // Implementar integração com PostHog, Mixpanel, etc
      // Por enquanto, apenas log
      console.log('[AICallLogger] Analytics event:', data);
    } catch (error) {
      console.error('[AICallLogger] Erro ao enviar analytics:', error);
    }
  }

  /**
   * Alertar equipe interna sobre problemas
   */
  private static async alertInternal(alert: {
    level: 'error' | 'warning' | 'info';
    message: string;
    data?: any;
  }): Promise<void> {
    try {
      // Implementar integração com Slack, PagerDuty, etc
      console.log(`[ALERT-${alert.level.toUpperCase()}] ${alert.message}`, alert.data);
    } catch (error) {
      console.error('[AICallLogger] Erro ao enviar alerta:', error);
    }
  }
}

export default AICallLogger;
