import type { BoxProps } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { MotionBox, type WithoutMotion } from '../../lib/motion';

export interface PageWrapperProps extends WithoutMotion<Omit<BoxProps, 'children'>> {
  children: ReactNode;
}

/** Every page is wrapped in this for a consistent, subtle fade-in. */
export function PageWrapper({ children, ...rest }: PageWrapperProps) {
  return (
    <MotionBox
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      w="full"
      {...rest}
    >
      {children}
    </MotionBox>
  );
}

export default PageWrapper;
