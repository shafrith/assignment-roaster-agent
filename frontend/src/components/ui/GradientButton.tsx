import type { ButtonProps } from '@chakra-ui/react';
import { forwardRef, type ReactNode } from 'react';
import { MotionButton, type WithoutMotion } from '../../lib/motion';

export type GradientButtonProps = WithoutMotion<Omit<ButtonProps, 'children'>> & { children?: ReactNode };

export const GradientButton = forwardRef<HTMLButtonElement, GradientButtonProps>(
  function GradientButton({ children, ...rest }, ref) {
    return (
      <MotionButton
        ref={ref}
        size="lg"
        px={8}
        color="white"
        bgGradient="linear(to-r, fire.400, fire.600, red.600)"
        boxShadow="0 8px 24px -8px rgba(249, 89, 15, 0.6)"
        _hover={{ bgGradient: 'linear(to-r, fire.300, fire.500, red.500)', boxShadow: '0 12px 32px -8px rgba(249, 89, 15, 0.8)' }}
        _active={{ bgGradient: 'linear(to-r, fire.500, fire.700, red.700)' }}
        whileHover={{ scale: 1.02, y: -2 }}
        whileTap={{ scale: 0.98 }}
        {...rest}
      >
        {children}
      </MotionButton>
    );
  },
);

export default GradientButton;
