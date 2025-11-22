import React from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

export function DeleteConfirmationModal({ item, onClose, onConfirm, open }) {
    const { t } = useTranslation();

    return (
        <Dialog open={open} onOpenChange={onClose}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{t('dashboard.delete')}</DialogTitle>
                    <DialogDescription>
                        {t('dashboard.confirmDelete')} <span className="font-semibold text-foreground">{item?.name}</span> ? {t('dashboard.deleteWarning')}
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>{t('dashboard.cancel')}</Button>
                    <Button variant="destructive" onClick={onConfirm}>{t('dashboard.confirm')}</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
