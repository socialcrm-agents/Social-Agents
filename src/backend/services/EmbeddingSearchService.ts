/**
 * EmbeddingSearchService.ts
 * Serviço de busca por embeddings (RAG - Retrieval Augmented Generation)
 * Busca apenas os trechos mais relevantes da base de conhecimento
 * Reduz drasticamente o consumo de tokens
 */

import * as db from '../db';

export interface SearchResult {
  id: number;
  title: string;
  content: string;
  relevanceScore: number; // 0-100
  embedding?: number[];
}

export class EmbeddingSearchService {
  /**
   * Buscar treinamentos relevantes para uma mensagem
   * Usa similaridade semântica para encontrar apenas o que importa
   */
  static async findRelevantTrainings(
    agentId: number,
    query: string,
    topK: number = 5,
    minRelevance: number = 0.7
  ): Promise<SearchResult[]> {
    try {
      // 1. Gerar embedding da query
      const queryEmbedding = await this.generateEmbedding(query);

      // 2. Buscar treinamentos do agente
      const trainings = await db
        .select()
        .from(trainingsTable)
        .where(eq(trainingsTable.agentId, agentId));

      if (trainings.length === 0) {
        console.log(`[EmbeddingSearch] Nenhum treinamento encontrado para agente ${agentId}`);
        return [];
      }

      // 3. Calcular similaridade com cada treinamento
      const scoredTrainings = await Promise.all(
        trainings.map(async training => {
          const trainingEmbedding = training.embedding
            ? JSON.parse(training.embedding)
            : await this.generateEmbedding(training.content);

          const similarity = this.cosineSimilarity(queryEmbedding, trainingEmbedding);
          const relevanceScore = Math.round(similarity * 100);

          return {
            id: training.id,
            title: training.title,
            content: training.content,
            relevanceScore,
            embedding: trainingEmbedding,
          };
        })
      );

      // 4. Filtrar por relevância mínima
      const relevant = scoredTrainings.filter(t => t.relevanceScore >= minRelevance * 100);

      // 5. Ordenar por relevância e retornar top K
      const topResults = relevant
        .sort((a, b) => b.relevanceScore - a.relevanceScore)
        .slice(0, topK);

      console.log(
        `[EmbeddingSearch] Query: "${query}" | Encontrados: ${topResults.length}/${trainings.length} | Top relevância: ${topResults[0]?.relevanceScore || 0}%`
      );

      return topResults;
    } catch (error) {
      console.error('[EmbeddingSearch] Erro ao buscar treinamentos:', error);
      // Fallback: retornar treinamentos aleatórios
      return this.fallbackSearch(agentId, topK);
    }
  }

  /**
   * Busca por fallback quando embedding falha
   */
  private static async fallbackSearch(agentId: number, topK: number): Promise<SearchResult[]> {
    try {
      const trainings = await db
        .select()
        .from(trainingsTable)
        .where(eq(trainingsTable.agentId, agentId))
        .limit(topK);

      return trainings.map(t => ({
        id: t.id,
        title: t.title,
        content: t.content,
        relevanceScore: 50, // Score padrão
      }));
    } catch (error) {
      console.error('[EmbeddingSearch] Erro no fallback:', error);
      return [];
    }
  }

  /**
   * Gerar embedding para um texto
   * Usa OpenAI Embeddings API
   */
  private static async generateEmbedding(text: string): Promise<number[]> {
    try {
      // Limitar tamanho do texto
      const truncatedText = text.substring(0, 8000);

      // Chamar OpenAI Embeddings API
      const response = await fetch('https://api.openai.com/v1/embeddings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          model: 'text-embedding-3-small', // Modelo mais rápido e barato
          input: truncatedText,
        }),
      });

      if (!response.ok) {
        throw new Error(`OpenAI API error: ${response.statusText}`);
      }

      const data = (await response.json()) as any;
      return data.data[0].embedding;
    } catch (error) {
      console.error('[EmbeddingSearch] Erro ao gerar embedding:', error);
      // Retornar embedding aleatório como fallback
      return Array(1536).fill(0).map(() => Math.random());
    }
  }

  /**
   * Calcular similaridade do cosseno entre dois vetores
   */
  private static cosineSimilarity(vecA: number[], vecB: number[]): number {
    if (vecA.length !== vecB.length) {
      console.warn('[EmbeddingSearch] Vetores com tamanhos diferentes');
      return 0;
    }

    let dotProduct = 0;
    let normA = 0;
    let normB = 0;

    for (let i = 0; i < vecA.length; i++) {
      dotProduct += vecA[i] * vecB[i];
      normA += vecA[i] * vecA[i];
      normB += vecB[i] * vecB[i];
    }

    normA = Math.sqrt(normA);
    normB = Math.sqrt(normB);

    if (normA === 0 || normB === 0) {
      return 0;
    }

    return dotProduct / (normA * normB);
  }

  /**
   * Pré-processar e armazenar embeddings para todos os treinamentos
   * Deve ser executado quando um novo treinamento é adicionado
   */
  static async generateAndStoreEmbedding(trainingId: number): Promise<void> {
    try {
      // Buscar treinamento
      const training = await db
        .select()
        .from(trainingsTable)
        .where(eq(trainingsTable.id, trainingId))
        .first();

      if (!training) {
        throw new Error(`Treinamento ${trainingId} não encontrado`);
      }

      // Gerar embedding
      const embedding = await this.generateEmbedding(training.content);

      // Armazenar no banco
      await db
        .update(trainingsTable)
        .set({ embedding: JSON.stringify(embedding) })
        .where(eq(trainingsTable.id, trainingId));

      console.log(`[EmbeddingSearch] Embedding armazenado para treinamento ${trainingId}`);
    } catch (error) {
      console.error('[EmbeddingSearch] Erro ao gerar e armazenar embedding:', error);
    }
  }

  /**
   * Gerar embeddings em lote para múltiplos treinamentos
   */
  static async generateBatchEmbeddings(agentId: number): Promise<void> {
    try {
      const trainings = await db
        .select()
        .from(trainingsTable)
        .where(eq(trainingsTable.agentId, agentId));

      console.log(
        `[EmbeddingSearch] Gerando embeddings para ${trainings.length} treinamentos...`
      );

      for (const training of trainings) {
        if (!training.embedding) {
          await this.generateAndStoreEmbedding(training.id);
          // Aguardar um pouco para não sobrecarregar a API
          await new Promise(resolve => setTimeout(resolve, 100));
        }
      }

      console.log(`[EmbeddingSearch] Batch de embeddings concluído para agente ${agentId}`);
    } catch (error) {
      console.error('[EmbeddingSearch] Erro ao gerar batch de embeddings:', error);
    }
  }

  /**
   * Obter estatísticas de embeddings
   */
  static async getEmbeddingStats(agentId: number): Promise<{
    totalTrainings: number;
    withEmbedding: number;
    withoutEmbedding: number;
    coverage: number;
  }> {
    try {
      const trainings = await db
        .select()
        .from(trainingsTable)
        .where(eq(trainingsTable.agentId, agentId));

      const withEmbedding = trainings.filter(t => t.embedding).length;
      const withoutEmbedding = trainings.length - withEmbedding;
      const coverage = trainings.length > 0 ? (withEmbedding / trainings.length) * 100 : 0;

      return {
        totalTrainings: trainings.length,
        withEmbedding,
        withoutEmbedding,
        coverage: Math.round(coverage),
      };
    } catch (error) {
      console.error('[EmbeddingSearch] Erro ao obter estatísticas:', error);
      return {
        totalTrainings: 0,
        withEmbedding: 0,
        withoutEmbedding: 0,
        coverage: 0,
      };
    }
  }
}

export default EmbeddingSearchService;
