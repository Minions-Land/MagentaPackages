/**
 * Cardiomni Brand Configuration
 *
 * Cardiovascular-inspired palette for medical imaging AI agent.
 * Mirrors the BrandConfig shape for Magenta3 brand activation.
 */

export interface BrandConfig {
  kind: 'brand';
  name: string;
  displayName: string;
  description: string;
  source: string;
  theme: ThemeConfig;
  cli?: CLIConfig;
}

export interface ThemeConfig {
  primaryColor: string;
  accentColor: string;
  successColor: string;
  warningColor: string;
  errorColor: string;
  linkColor: string;
  mutedColor: string;
  panelColor: string;
}

export interface CLIConfig {
  binaryName: string;
  description: string;
  welcomeMessage: string;
  prompt: string;
}

export const CardiomniBrand: BrandConfig = {
  kind: 'brand',
  name: 'Cardiomni',
  displayName: 'Cardiomni',
  description: 'Cardiomni package brand inspired by cardiovascular medical imaging and clinical interfaces.',
  source: 'Cardiomni',
  theme: {
    primaryColor: '#C41E3A',      // Crimson Red - cardiovascular focus
    accentColor: '#2E86AB',       // Clinical Blue - medical imaging
    successColor: '#06A77D',      // Healthy Green - good perfusion
    warningColor: '#F77F00',      // Amber - clinical alerts
    errorColor: '#D62828',        // Alert Red
    linkColor: '#0077BE',         // Medical Blue
    mutedColor: '#8B8B8B',        // Neutral Gray
    panelColor: '#1A1A1A',        // Dark clinical interface
  },
  cli: {
    binaryName: 'cardiomni',
    description: 'Cardiovascular AI agent for CTA/DSA stenosis assessment',
    welcomeMessage: 'Welcome to Cardiomni - Cardiovascular Intelligence',
    prompt: 'cardiomni>',
  },
};

export default CardiomniBrand;
