import { FaGithub } from 'react-icons/fa';
import { useAuth } from '../../hooks/useAuth';
import { GradientButton, type GradientButtonProps } from '../ui/GradientButton';

export type GitHubLoginButtonProps = Omit<GradientButtonProps, 'onClick' | 'leftIcon'> & {
  label?: string;
};

/** Starts the GitHub OAuth flow via a full-page navigation. */
export function GitHubLoginButton({ label = 'Login with GitHub', ...rest }: GitHubLoginButtonProps) {
  const { login } = useAuth();
  return (
    <GradientButton leftIcon={<FaGithub />} onClick={login} {...rest}>
      {label}
    </GradientButton>
  );
}

export default GitHubLoginButton;
