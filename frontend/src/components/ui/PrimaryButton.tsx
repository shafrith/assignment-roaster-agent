import { Button, type ButtonProps } from '@chakra-ui/react';
import { forwardRef } from 'react';

export type PrimaryButtonProps = ButtonProps;

/** Main call-to-action button: solid blue. */
export const PrimaryButton = forwardRef<HTMLButtonElement, PrimaryButtonProps>(
  function PrimaryButton({ children, ...rest }, ref) {
    return (
      <Button ref={ref} size="lg" px={8} colorScheme="brand" {...rest}>
        {children}
      </Button>
    );
  },
);

export default PrimaryButton;
