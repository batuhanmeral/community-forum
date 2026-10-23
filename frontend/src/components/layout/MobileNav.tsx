import { useEffect, useId, useRef, type MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { SidebarNav } from './Sidebar';
import { X } from 'lucide-react';

interface MobileNavProps {
  open: boolean;
  onClose: () => void;
}

const closeIcon = (
  <X className="h-[18px] w-[18px]" />
);

export function MobileNav({ open, onClose }: MobileNavProps) {
  const { t } = useTranslation();
  const titleId = useId();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const pressedOnBackdrop = useRef(false);

  // showModal() gives inert background, Escape and focus return without custom code.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);

  // A modal <dialog> doesn't stop the page behind it from scrolling on touch devices.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // The panel fills the dialog box, so only a click on the ::backdrop targets the dialog itself.
  // A drag that starts in the panel and ends on the backdrop is not a backdrop click.
  function handleClick(e: MouseEvent<HTMLDialogElement>) {
    if (e.target === e.currentTarget && pressedOnBackdrop.current) onClose();
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      onClose={onClose}
      onPointerDown={(e) => (pressedOnBackdrop.current = e.target === e.currentTarget)}
      onClick={handleClick}
      className="m-0 h-dvh max-h-none w-[280px] max-w-[85vw] border-r border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)] p-0 text-[var(--color-text)] backdrop:bg-[var(--color-overlay)]"
    >
      <div className="flex h-full flex-col overflow-y-auto overscroll-contain px-2 pb-10 pt-3">
        <div className="mb-3 flex items-center justify-between pl-3">
          <h2 id={titleId} className="text-[10.5px] font-medium uppercase tracking-[0.12em] text-[var(--color-text-dim)]">
            {t('nav.menu')}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('nav.closeMenu')}
            className="grid h-[38px] w-[38px] place-items-center rounded-[11px] text-[var(--color-text-soft)] transition hover:bg-[var(--color-bg-3)] hover:text-[var(--color-text)]"
          >
            {closeIcon}
          </button>
        </div>
        {open && <SidebarNav onNavigate={onClose} />}
      </div>
    </dialog>
  );
}
