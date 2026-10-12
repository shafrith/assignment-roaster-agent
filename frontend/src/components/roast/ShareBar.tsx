import { Button, HStack, Text, VStack, Wrap, WrapItem, useToast } from '@chakra-ui/react';
import { FaWhatsapp, FaXTwitter } from 'react-icons/fa6';
import { FiCopy } from 'react-icons/fi';
import { buildPublicRoastUrl, buildShareText, buildWhatsAppShareUrl, buildXShareUrl } from '../../lib/format';

export interface ShareBarProps {
  shareSlug: string;
  score: number;
  /** Share buttons are disabled when the roast is private. */
  isPublic: boolean;
}

export function ShareBar({ shareSlug, score, isPublic }: ShareBarProps) {
  const toast = useToast();
  const url = buildPublicRoastUrl(shareSlug);
  const text = buildShareText(score);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      toast({ title: 'Link copy aayiduchu! 📋', status: 'success', duration: 2500 });
    } catch {
      toast({ title: 'Copy panna mudiyala 😕', description: url, status: 'error', duration: 5000 });
    }
  };

  return (
    <VStack align="stretch" spacing={2} data-testid="share-bar">
      <Wrap spacing={2}>
        <WrapItem>
          <Button
            leftIcon={<FiCopy aria-hidden="true" />}
            variant="outline"
            size="sm"
            onClick={() => void handleCopy()}
            isDisabled={!isPublic}
            aria-label="Copy public roast link"
          >
            Copy link
          </Button>
        </WrapItem>
        <WrapItem>
          <Button
            as="a"
            href={isPublic ? buildWhatsAppShareUrl(text, url) : undefined}
            target="_blank"
            rel="noopener noreferrer"
            leftIcon={<FaWhatsapp aria-hidden="true" />}
            colorScheme="green"
            size="sm"
            isDisabled={!isPublic}
            aria-disabled={!isPublic}
            aria-label="Share on WhatsApp"
          >
            WhatsApp
          </Button>
        </WrapItem>
        <WrapItem>
          <Button
            as="a"
            href={isPublic ? buildXShareUrl(text, url) : undefined}
            target="_blank"
            rel="noopener noreferrer"
            leftIcon={<FaXTwitter aria-hidden="true" />}
            colorScheme="gray"
            size="sm"
            isDisabled={!isPublic}
            aria-disabled={!isPublic}
            aria-label="Share on X"
          >
            Post on X
          </Button>
        </WrapItem>
      </Wrap>
      {!isPublic && (
        <HStack>
          <Text fontSize="sm" color="text.muted">
            🔒 Private roast. Share panna mudhalla public-a maathu.
          </Text>
        </HStack>
      )}
    </VStack>
  );
}

export default ShareBar;
