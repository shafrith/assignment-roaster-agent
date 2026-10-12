import type { BoxProps } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { MotionBox, type WithoutMotion } from '../../lib/motion';

export interface GlassCardProps extends WithoutMotion<Omit<BoxProps, 'children'>> {
  children: ReactNode;
  /** Disable the hover lift (e.g. for large static containers). */
  disableHover?: boolean;
}

export function GlassCard({ children, disableHover = false, ...rest }: GlassCardProps) {
  return (
    <MotionBox
      layerStyle="glass"
      p={6}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={disableHover ? undefined : { scale: 1.02, y: -5 }}
      transition={{ type: 'spring', stiffness: 260, damping: 22 }}
      {...rest}
    >
      {children}
    </MotionBox>
  );
}

export default GlassCard;
