import { Box, type BoxProps } from '@chakra-ui/react';
import type { ReactNode } from 'react';

export interface PanelProps extends Omit<BoxProps, 'children'> {
  children: ReactNode;
}

/** Flat white card with a thin gray border (no shadow, blur or hover effects). */
export function Panel({ children, ...rest }: PanelProps) {
  return (
    <Box layerStyle="card" p={6} {...rest}>
      {children}
    </Box>
  );
}

export default Panel;
