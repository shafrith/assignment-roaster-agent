import type { BoxProps } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { MotionBox, type WithoutMotion } from '../../lib/motion';

export interface PageWrapperProps extends WithoutMotion<Omit<BoxProps, 'children'>> {
  children: ReactNode;
}

/** Every page is wrapped in this for a consistent fade/slide-in. */
export function PageWrapper({ children, ...rest }: PageWrapperProps) {
  return (
    <MotionBox
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.3 }}
      w="full"
      {...rest}
    >
      {children}
    </MotionBox>
  );
}

export default PageWrapper;
