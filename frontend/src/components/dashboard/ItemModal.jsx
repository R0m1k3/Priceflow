import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const API_URL = '/api';

export function ItemModal({ item, onClose, onSaved, open }) {
    const { t } = useTranslation();
    const [formData, setFormData] = useState({
        url: '',
        name: '',
        target_price: '',
        selector: '',
        tags: '',
        description: '',
        notification_profile_id: ''
    });
    const [profiles, setProfiles] = useState([]);

    useEffect(() => {
        if (item) {
            setFormData({
                url: item.url || '',
                name: item.name || '',
                target_price: item.target_price || '',
                selector: item.selector || '',
                tags: item.tags || '',
                description: item.description || '',
                notification_profile_id: item.notification_profile_id ? item.notification_profile_id.toString() : ''
            });
        } else {
            setFormData({
                url: '',
                name: '',
                target_price: '',
                selector: '',
                tags: '',
                description: '',
                notification_profile_id: ''
            });
        }
    }, [item, open]);

    useEffect(() => {
        if (open) {
            axios.get(`${API_URL}/notification-profiles`).then(res => setProfiles(res.data)).catch(console.error);
        }
    }, [open]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const payload = {
                ...formData,
                target_price: formData.target_price ? parseFloat(formData.target_price) : null,
                notification_profile_id: formData.notification_profile_id ? parseInt(formData.notification_profile_id) : null
            };

            if (item) {
                await axios.put(`${API_URL}/items/${item.id}`, payload);
                toast.success(t('toast.itemUpdated'));
            } else {
                await axios.post(`${API_URL}/items`, payload);
                toast.success(t('toast.itemCreated'));
            }
            onSaved();
            onClose();
        } catch (error) {
            console.error('Error saving item:', error);
            toast.error(t('toast.itemError'));
        }
    };

    return (
        <Dialog open={open} onOpenChange={onClose}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>{item ? t('itemModal.editTitle') : t('itemModal.addTitle')}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 py-4">
                    <div className="space-y-2">
                        <Label htmlFor="url">{t('itemModal.url')}</Label>
                        <Input
                            id="url"
                            type="url"
                            required
                            placeholder={t('itemModal.urlPlaceholder')}
                            value={formData.url}
                            onChange={e => setFormData({ ...formData, url: e.target.value })}
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="name">{t('itemModal.name')}</Label>
                        <Input
                            id="name"
                            required
                            placeholder={t('itemModal.namePlaceholder')}
                            value={formData.name}
                            onChange={e => setFormData({ ...formData, name: e.target.value })}
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="target_price">{t('itemModal.targetPrice')} (€)</Label>
                            <Input
                                id="target_price"
                                type="number"
                                step="0.01"
                                placeholder="0.00"
                                value={formData.target_price}
                                onChange={e => setFormData({ ...formData, target_price: e.target.value })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="selector">{t('itemModal.selector')}</Label>
                            <Input
                                id="selector"
                                placeholder={t('itemModal.selectorPlaceholder')}
                                value={formData.selector}
                                onChange={e => setFormData({ ...formData, selector: e.target.value })}
                            />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="profile">{t('itemModal.notificationProfile')}</Label>
                        <Select
                            value={formData.notification_profile_id}
                            onValueChange={(value) => setFormData({ ...formData, notification_profile_id: value })}
                        >
                            <SelectTrigger>
                                <SelectValue placeholder={t('itemModal.selectProfile')} />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="none">{t('itemModal.noProfile')}</SelectItem>
                                {profiles.map(p => (
                                    <SelectItem key={p.id} value={p.id.toString()}>{p.name}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="tags">{t('itemModal.tags')}</Label>
                        <Input
                            id="tags"
                            placeholder={t('itemModal.tagsPlaceholder')}
                            value={formData.tags}
                            onChange={e => setFormData({ ...formData, tags: e.target.value })}
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="description">{t('itemModal.description')}</Label>
                        <textarea
                            id="description"
                            className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                            placeholder={t('itemModal.descriptionPlaceholder')}
                            value={formData.description}
                            onChange={e => setFormData({ ...formData, description: e.target.value })}
                        />
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={onClose}>{t('common.cancel')}</Button>
                        <Button type="submit">{t('itemModal.save')}</Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
