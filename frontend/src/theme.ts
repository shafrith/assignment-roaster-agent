import { extendTheme, type ThemeConfig } from '@chakra-ui/react';

const config: ThemeConfig = {
  initialColorMode: 'dark',
  useSystemColorMode: false,
};

/** "Fire" palette: amber/orange (low) → red (high). */
const fire = {
  50: '#fff4e6',
  100: '#ffe0b8',
  200: '#ffc285',
  300: '#ffa052',
  400: '#ff7f2a',
  500: '#f9590f',
  600: '#e0400b',
  700: '#b82d0b',
  800: '#8f2010',
  900: '#661610',
};

export const theme = extendTheme({
  config,
  colors: {
    fire,
    brand: fire,
    ember: {
      900: '#0d0a09',
      800: '#15100e',
      700: '#1e1714',
      600: '#2a201c',
    },
  },
  fonts: {
    heading: `'Space Grotesk', 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif`,
    body: `'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`,
    mono: `'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, monospace`,
  },
  semanticTokens: {
    colors: {
      'bg.canvas': { default: 'gray.50', _dark: 'ember.900' },
      'bg.surface': { default: 'white', _dark: 'ember.800' },
      'bg.glass': { default: 'blackAlpha.50', _dark: 'whiteAlpha.100' },
      'border.glass': { default: 'blackAlpha.200', _dark: 'whiteAlpha.200' },
      'text.muted': { default: 'gray.600', _dark: 'gray.400' },
      accent: { default: 'fire.600', _dark: 'fire.400' },
    },
  },
  styles: {
    global: {
      'html, body': {
        bg: 'bg.canvas',
        color: 'chakra-body-text',
        minHeight: '100vh',
      },
      '::selection': {
        bg: 'fire.500',
        color: 'white',
      },
    },
  },
  components: {
    Button: {
      defaultProps: { colorScheme: 'fire' },
      baseStyle: { borderRadius: 'full', fontWeight: 'semibold' },
    },
    Link: {
      baseStyle: { _hover: { textDecoration: 'none', color: 'accent' } },
    },
  },
  layerStyles: {
    glass: {
      bg: 'bg.glass',
      backdropFilter: 'blur(16px)',
      border: '1px solid',
      borderColor: 'border.glass',
      borderRadius: '2xl',
      boxShadow: 'xl',
    },
  },
  textStyles: {
    fireGradient: {
      bgGradient: 'linear(to-r, fire.300, fire.500, red.500)',
      bgClip: 'text',
    },
  },
});

export default theme;
