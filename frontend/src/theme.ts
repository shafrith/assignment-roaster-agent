import { extendTheme, theme as baseTheme, type ThemeConfig } from '@chakra-ui/react';

/** Light mode only: the UI is two colors — white and one blue — plus neutral gray text. */
const config: ThemeConfig = {
  initialColorMode: 'light',
  useSystemColorMode: false,
};

export const theme = extendTheme({
  config,
  colors: {
    brand: baseTheme.colors.blue,
  },
  fonts: {
    heading: `'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif`,
    body: `'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`,
    mono: `'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, monospace`,
  },
  semanticTokens: {
    colors: {
      'bg.canvas': 'white',
      'bg.surface': 'white',
      'bg.subtle': 'gray.50',
      'border.subtle': 'gray.200',
      'text.muted': 'gray.600',
      accent: 'brand.600',
    },
  },
  styles: {
    global: {
      'html, body': {
        bg: 'bg.canvas',
        color: 'gray.800',
        minHeight: '100vh',
      },
      '::selection': {
        bg: 'brand.100',
      },
    },
  },
  components: {
    Button: {
      defaultProps: { colorScheme: 'brand' },
      baseStyle: { borderRadius: 'md', fontWeight: 'semibold' },
    },
    Badge: {
      defaultProps: { colorScheme: 'brand' },
    },
    Tag: {
      defaultProps: { colorScheme: 'brand' },
    },
    // Validation messages stay within the two-color palette (no red).
    FormError: {
      baseStyle: { text: { color: 'brand.700' }, icon: { color: 'brand.700' } },
    },
    Link: {
      baseStyle: { _hover: { textDecoration: 'none', color: 'accent' } },
    },
  },
  layerStyles: {
    card: {
      bg: 'bg.surface',
      border: '1px solid',
      borderColor: 'border.subtle',
      borderRadius: 'lg',
    },
  },
  textStyles: {
    accent: {
      color: 'accent',
    },
  },
});

export default theme;
