import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { fetchArtifact } from '../../services/api';
import { valueAtKeys, type ImageSummary } from '../../utils/imageFields';
import styles from './ImageThumbnails.module.css';

interface ImageThumbnailsProps {
  artifactId: string;
  images: ImageSummary[];
}

interface OpenImage {
  id: string; // from the key segments: display paths can look alike
  path: string;
  url?: string;
  error?: string;
}

const sizeLabel = (bytes: number) => `${Math.max(1, Math.round(bytes / 1024))} KB`;

const imageId = (image: ImageSummary) => JSON.stringify(image.keys ?? [image.path]);

/** The full image in a modal: focus on Close, Tab stays there, Escape closes. */
const FullImageDialog: React.FC<{ image: OpenImage; onClose: () => void }> = ({ image, onClose }) => {
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        onClose();
      } else if (event.key === 'Tab') {
        // Modal: the close button is the only control, keep focus on it
        event.preventDefault();
        closeRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown, { capture: true });
    return () => window.removeEventListener('keydown', onKeyDown, { capture: true });
  }, [onClose]);

  // Take focus from the thumbnail that opened the dialog and give it back on close
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    return () => opener?.focus();
  }, []);

  // In document.body: detail windows are transformed, which would confine a fixed overlay
  return createPortal(
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label={`${image.path} full size`}>
      <div className={styles.dialog}>
        <div className={styles.dialogHeader}>
          <span>{image.path}</span>
          <button type="button" ref={closeRef} onClick={onClose} aria-label="Close" className={styles.close}>
            ×
          </button>
        </div>
        {image.url && <img src={image.url} alt={`${image.path} (full size)`} className={styles.full} />}
        {image.error && <p className={styles.message}>{image.error}</p>}
        {!image.url && !image.error && <p className={styles.message}>Loading…</p>}
      </div>
    </div>,
    document.body
  );
};

/**
 * Previews of an artifact's images (#512). The dashboard receives small thumbnails;
 * the full image is loaded only when one is opened, through the artifact endpoint,
 * which applies the artifact's visibility.
 */
const ImageThumbnails: React.FC<ImageThumbnailsProps> = ({ artifactId, images }) => {
  const [open, setOpen] = useState<OpenImage | null>(null);

  const openImage = async (image: ImageSummary) => {
    const { path } = image;
    const id = imageId(image);
    setOpen({ id, path });
    try {
      const artifact = await fetchArtifact(artifactId);
      const url = valueAtKeys(artifact.payload, image.keys ?? [path])?.url;
      if (typeof url !== 'string' || !url.startsWith('data:image/')) {
        throw new Error('no image at this location');
      }
      setOpen((current) => (current?.id === id ? { id, path, url } : current));
    } catch {
      setOpen((current) =>
        current?.id === id
          ? { id, path, error: 'Could not load the full image (it may be gone or not visible to you).' }
          : current
      );
    }
  };

  if (images.length === 0) return null;

  return (
    <>
      <div className={styles.thumbnails}>
        {images.map((image) => (
          <figure key={imageId(image)} className={styles.thumbnail}>
            <button
              type="button"
              className={styles.thumbnailButton}
              onClick={() => void openImage(image)}
              aria-label={`Open ${image.path}`}
              title="Open the full image"
            >
              <img src={image.thumb} alt={image.path} />
            </button>
            <figcaption className={styles.caption}>
              {image.path} · {image.mime} · {sizeLabel(image.bytes)}
            </figcaption>
          </figure>
        ))}
      </div>
      {open && <FullImageDialog image={open} onClose={() => setOpen(null)} />}
    </>
  );
};

export default ImageThumbnails;
