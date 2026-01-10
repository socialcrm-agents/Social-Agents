/**
 * OptimizedPromptBuilder.ts
 * Construtor de prompts otimizado com:
 * - Estrutura XML consistente
 * - Few-shot examples
 * - Contexto relevante apenas
 * - Instruções claras e estruturadas
 */

import type { Agent, Training, Message } from '../../drizzle/schema';

export interface PromptContext {
  agent: Agent;
  relevantTrainings: Training[];
  conversationHistory: Message[];
  contactName: string;
  contactPhone: string;
  currentMessage: string;
}

export interface OptimizedPromptResult {
  prompt: string;
  length: number;
  estimatedTokens: number;
  sections: string[];
}

export class OptimizedPromptBuilder {
  /**
   * Construir prompt otimizado com estrutura XML
   */
  static buildOptimizedPrompt(context: PromptContext): OptimizedPromptResult {
    const sections: string[] = [];
    let prompt = '';

    // ============================================================================
    // SEÇÃO 1: DEFINIÇÃO DE TAREFA E IDENTIDADE
    // ============================================================================
    prompt += this.buildTaskDefinition(context.agent);
    sections.push('task_definition');

    // ============================================================================
    // SEÇÃO 2: BASE DE CONHECIMENTO (APENAS RELEVANTE)
    // ============================================================================
    if (context.relevantTrainings.length > 0) {
      prompt += this.buildKnowledgeBase(context.relevantTrainings);
      sections.push('knowledge_base');
    }

    // ============================================================================
    // SEÇÃO 3: HISTÓRICO DA CONVERSA (ÚLTIMAS 10 MENSAGENS)
    // ============================================================================
    if (context.conversationHistory.length > 0) {
      prompt += this.buildConversationHistory(
        context.conversationHistory,
        context.agent,
        context.contactName
      );
      sections.push('conversation_history');
    }

    // ============================================================================
    // SEÇÃO 4: EXEMPLOS (FEW-SHOT)
    // ============================================================================
    prompt += this.buildFewShotExamples(context.agent.purpose);
    sections.push('few_shot_examples');

    // ============================================================================
    // SEÇÃO 5: REGRAS E RESTRIÇÕES
    // ============================================================================
    prompt += this.buildRulesAndConstraints(context.agent);
    sections.push('rules_and_constraints');

    // ============================================================================
    // SEÇÃO 6: CONTEXTO DO CLIENTE
    // ============================================================================
    prompt += this.buildClientContext(context.contactName, context.contactPhone);
    sections.push('client_context');

    // ============================================================================
    // SEÇÃO 7: MENSAGEM A RESPONDER
    // ============================================================================
    prompt += this.buildCurrentMessage(context.currentMessage, context.contactName);
    sections.push('current_message');

    // ============================================================================
    // SEÇÃO 8: INSTRUÇÕES FINAIS
    // ============================================================================
    prompt += this.buildFinalInstructions();
    sections.push('final_instructions');

    return {
      prompt,
      length: prompt.length,
      estimatedTokens: Math.ceil(prompt.length / 4), // Aproximação
      sections,
    };
  }

  /**
   * Construir definição de tarefa
   */
  private static buildTaskDefinition(agent: Agent): string {
    return `<?xml version="1.0" encoding="UTF-8"?>
<task>
  <objective>
    Você é ${agent.name}, um agente de IA especialista em ${this.getPurposeDescription(agent.purpose)}.
    Seu estilo de comunicação é ${this.getStyleDescription(agent.communicationStyle)}.
    ${agent.description ? `Descrição: ${agent.description}` : ''}
  </objective>

  <business_context>
    ${agent.productName ? `Produto/Serviço: ${agent.productName}` : ''}
    ${agent.productDescription ? `Descrição: ${agent.productDescription}` : ''}
    ${agent.websiteUrl ? `Website: ${agent.websiteUrl}` : ''}
  </business_context>

`;
  }

  /**
   * Construir base de conhecimento
   */
  private static buildKnowledgeBase(trainings: Training[]): string {
    let kb = `  <knowledge_base>
    <summary>Use APENAS as informações abaixo para responder. Cite a fonte quando usar.</summary>
`;

    trainings.slice(0, 5).forEach((training, idx) => {
      const content = training.content.substring(0, 500); // Limitar tamanho
      kb += `    <document index="${idx + 1}" title="${training.title}">
${content}
    </document>
`;
    });

    kb += `    <instructions>
      - Baseie sua resposta SEMPRE na base de conhecimento
      - Se a resposta está no documento, cite qual documento
      - Se não encontrar, diga: "Deixe-me conectar você com um especialista"
      - NUNCA invente informações
    </instructions>
  </knowledge_base>

`;
    return kb;
  }

  /**
   * Construir histórico da conversa
   */
  private static buildConversationHistory(
    messages: Message[],
    agent: Agent,
    contactName: string
  ): string {
    // Pegar apenas as últimas 10 mensagens para não inchar o prompt
    const recentMessages = messages.slice(-10);

    let history = `  <conversation_history>
    <client_name>${contactName}</client_name>
    <messages>
`;

    recentMessages.forEach(msg => {
      const sender = msg.direction === 'incoming' ? contactName : agent.name;
      history += `      <message from="${sender}">${msg.content}</message>
`;
    });

    history += `    </messages>
  </conversation_history>

`;
    return history;
  }

  /**
   * Construir exemplos (few-shot)
   */
  private static buildFewShotExamples(purpose: string): string {
    const examples: Record<string, Array<{ user: string; agent: string }>> = {
      suporte: [
        {
          user: 'Não consigo fazer login',
          agent: 'Entendo sua frustração. Vamos resolver isso juntos. Você consegue me dizer qual é a mensagem de erro que aparece?',
        },
        {
          user: 'Qual é o preço?',
          agent: 'Nossos planos começam em R$ 99/mês. Qual seria melhor para você?',
        },
      ],
      vendas: [
        {
          user: 'Vocês têm alguma promoção?',
          agent: 'Sim! Para novos clientes, oferecemos 30% de desconto no primeiro mês. Quer saber mais?',
        },
        {
          user: 'Como funciona?',
          agent: 'É simples: 1) Crie um agente, 2) Treine com seus dados, 3) Integre ao WhatsApp. Começamos agora?',
        },
      ],
      uso_pessoal: [
        {
          user: 'Me ajuda a planejar meu dia?',
          agent: 'Claro! Qual é sua prioridade principal hoje? Vamos organizar juntos.',
        },
      ],
    };

    const exampleList = examples[purpose] || examples.suporte;

    let examplesXml = `  <few_shot_examples>
    <instruction>Aqui estão exemplos de como responder. Siga este padrão.</instruction>
`;

    exampleList.forEach((ex, idx) => {
      examplesXml += `    <example index="${idx + 1}">
      <user_message>${ex.user}</user_message>
      <expected_response>${ex.agent}</expected_response>
    </example>
`;
    });

    examplesXml += `  </few_shot_examples>

`;
    return examplesXml;
  }

  /**
   * Construir regras e restrições
   */
  private static buildRulesAndConstraints(agent: Agent): string {
    return `  <rules_and_constraints>
    <rule priority="critical">Responda em MÁXIMO 4 linhas. Seja conciso.</rule>
    <rule priority="critical">NUNCA invente informações. Use apenas a base de conhecimento.</rule>
    <rule priority="high">Leia TODO o contexto antes de responder.</rule>
    <rule priority="high">Se não souber, escale para um especialista.</rule>
    <rule priority="high">Mantenha seu estilo de comunicação: ${this.getStyleDescription(agent.communicationStyle)}</rule>
    <rule priority="medium">Seja empático e profissional.</rule>
    <rule priority="medium">Não se reapresente após a primeira mensagem.</rule>
  </rules_and_constraints>

`;
  }

  /**
   * Construir contexto do cliente
   */
  private static buildClientContext(contactName: string, contactPhone: string): string {
    return `  <client_context>
    <name>${contactName || 'Cliente'}</name>
    <phone>${contactPhone}</phone>
  </client_context>

`;
  }

  /**
   * Construir mensagem atual
   */
  private static buildCurrentMessage(currentMessage: string, contactName: string): string {
    return `  <current_message_to_respond>
    <from>${contactName}</from>
    <text>${currentMessage}</text>
  </current_message_to_respond>

`;
  }

  /**
   * Construir instruções finais
   */
  private static buildFinalInstructions(): string {
    return `  <final_instructions>
    <step1>Leia TODO o contexto acima</step1>
    <step2>Identifique a pergunta principal</step2>
    <step3>Busque a resposta na base de conhecimento</step3>
    <step4>Responda de forma concisa (máximo 4 linhas)</step4>
    <step5>Cite a fonte se usou a base de conhecimento</step5>
    <step6>Se não souber, escale para especialista</step6>
  </final_instructions>
</task>`;
  }

  /**
   * Obter descrição do propósito
   */
  private static getPurposeDescription(purpose: string): string {
    const descriptions: Record<string, string> = {
      suporte: 'fornecer suporte e resolver problemas dos clientes',
      vendas: 'identificar necessidades e vender soluções',
      uso_pessoal: 'ser um assistente pessoal confiável',
    };
    return descriptions[purpose] || 'atender os clientes';
  }

  /**
   * Obter descrição do estilo
   */
  private static getStyleDescription(style: string): string {
    const descriptions: Record<string, string> = {
      formal: 'profissional mas genuíno',
      normal: 'amigável e profissional',
      descontraida: 'casual e próximo',
    };
    return descriptions[style] || 'normal';
  }

  /**
   * Estimar tokens (aproximação)
   */
  static estimateTokens(text: string): number {
    // Aproximação: 1 token ≈ 4 caracteres
    return Math.ceil(text.length / 4);
  }

  /**
   * Validar tamanho do prompt
   */
  static validatePromptSize(prompt: string, maxTokens: number = 4000): {
    isValid: boolean;
    estimatedTokens: number;
    remaining: number;
  } {
    const estimatedTokens = this.estimateTokens(prompt);
    return {
      isValid: estimatedTokens < maxTokens,
      estimatedTokens,
      remaining: maxTokens - estimatedTokens,
    };
  }
}

export default OptimizedPromptBuilder;
