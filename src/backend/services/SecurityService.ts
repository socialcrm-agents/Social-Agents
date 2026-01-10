/**
 * SecurityService.ts
 * Serviço centralizado para operações de segurança
 * - Hashing e verificação de senhas
 * - Geração de tokens seguros
 * - Validação de dados sensíveis
 */

import * as bcrypt from 'bcrypt';
import * as crypto from 'crypto';

const SALT_ROUNDS = 12; // Aumentado para melhor segurança
const TOKEN_LENGTH = 32;

export class SecurityService {
  /**
   * Hash de senha com bcrypt
   * @param password - Senha em texto plano
   * @returns Promise com hash da senha
   */
  static async hashPassword(password: string): Promise<string> {
    if (!password || password.length < 6) {
      throw new Error('Senha deve ter no mínimo 6 caracteres');
    }

    try {
      const hash = await bcrypt.hash(password, SALT_ROUNDS);
      return hash;
    } catch (error) {
      console.error('[SecurityService] Erro ao fazer hash da senha:', error);
      throw new Error('Erro ao processar senha');
    }
  }

  /**
   * Verificar senha contra hash
   * @param password - Senha em texto plano
   * @param hash - Hash armazenado
   * @returns Promise<boolean>
   */
  static async verifyPassword(password: string, hash: string): Promise<boolean> {
    try {
      const isValid = await bcrypt.compare(password, hash);
      return isValid;
    } catch (error) {
      console.error('[SecurityService] Erro ao verificar senha:', error);
      return false;
    }
  }

  /**
   * Gerar token seguro para verificação de email
   * @returns Token aleatório seguro
   */
  static generateSecureToken(): string {
    return crypto.randomBytes(TOKEN_LENGTH).toString('hex');
  }

  /**
   * Gerar código de referência único
   * @returns Código aleatório para referências
   */
  static generateReferralCode(): string {
    return crypto.randomBytes(8).toString('hex').toUpperCase();
  }

  /**
   * Sanitizar dados sensíveis antes de enviar a terceiros
   * @param data - Objeto com dados potencialmente sensíveis
   * @returns Objeto sem dados sensíveis
   */
  static sanitizeForThirdParty(data: any): any {
    const sanitized = { ...data };
    
    // Lista de campos que NUNCA devem ser enviados
    const forbiddenFields = [
      'password',
      'passwordHash',
      'apiKey',
      'secretKey',
      'token',
      'refreshToken',
      'ssn',
      'creditCard',
    ];

    forbiddenFields.forEach(field => {
      delete sanitized[field];
    });

    return sanitized;
  }

  /**
   * Validar força da senha
   * @param password - Senha a validar
   * @returns Objeto com resultado e mensagens
   */
  static validatePasswordStrength(password: string): {
    isStrong: boolean;
    score: number;
    feedback: string[];
  } {
    const feedback: string[] = [];
    let score = 0;

    if (!password) {
      return { isStrong: false, score: 0, feedback: ['Senha é obrigatória'] };
    }

    // Comprimento
    if (password.length >= 8) score += 1;
    else feedback.push('Senha deve ter no mínimo 8 caracteres');

    if (password.length >= 12) score += 1;

    // Maiúsculas
    if (/[A-Z]/.test(password)) score += 1;
    else feedback.push('Adicione letras maiúsculas');

    // Minúsculas
    if (/[a-z]/.test(password)) score += 1;
    else feedback.push('Adicione letras minúsculas');

    // Números
    if (/\d/.test(password)) score += 1;
    else feedback.push('Adicione números');

    // Caracteres especiais
    if (/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) score += 1;
    else feedback.push('Adicione caracteres especiais');

    return {
      isStrong: score >= 4,
      score,
      feedback,
    };
  }

  /**
   * Validar email
   * @param email - Email a validar
   * @returns boolean
   */
  static validateEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  /**
   * Validar telefone (formato brasileiro)
   * @param phone - Telefone a validar
   * @returns boolean
   */
  static validatePhoneNumber(phone: string): boolean {
    // Remove caracteres não numéricos
    const cleaned = phone.replace(/\D/g, '');
    // Valida formato: 11 dígitos (com 9 dígito) ou 10 dígitos
    return /^(\d{10}|\d{11})$/.test(cleaned);
  }

  /**
   * Gerar hash para rastreamento (sem reversibilidade)
   * @param data - Dados a fazer hash
   * @returns Hash SHA-256
   */
  static generateHash(data: string): string {
    return crypto
      .createHash('sha256')
      .update(data)
      .digest('hex');
  }
}

export default SecurityService;
