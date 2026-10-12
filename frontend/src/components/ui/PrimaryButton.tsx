import type { ButtonProps } from '@chakra-ui/react';
import { forwardRef, type ReactNode } from 'react';
import { MotionButton, type WithoutMotion } from '../../lib/motion';

export type PrimaryButtonProps = WithoutMotion<Omit<ButtonProps, 'children'>> & { children?: ReactNode };

/** Main call-to-action button: solid fire color (no gradients). */
export const PrimaryButton = forwardRef<HTMLButtonElement, PrimaryButtonProps>(
  function PrimaryButton({ children, ...rest }, ref) {
    return (
      <MotionButton
        ref={ref}
        size="lg"
        px={8}
        color="white"
        bg="fire.500"
        _hover={{ bg: 'fire.600' }}
        _active={{ bg: 'fire.700' }}
        whileHover={{ scale: 1.02, y: -2 }}
        whileTap={{ scale: 0.98 }}
        {...rest}
      >
        {children}
      </MotionButton>
    );
  },
);

export default PrimaryButton;
