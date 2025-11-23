import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { X } from 'lucide-react';

const API_URL = '/api';

export function ItemModal({ item, onClose, onSaved, open, categories = [] }) {
    const { t } = useTranslation();
    const [formData, setFormData] = useState({
        url: '',
        name: '',
        target_price: '',
        tags: '',
        description: '',
        notification_channel_id: 'none',
        category: ''
    });
    const [channels, setChannels] = useState([]);
    const [showCustomInput, setShowCustomInput] = useState(false);

    useEffect(() => {
        const fetchChannels = async () => {
            try {
                const response = await axios.get(`${API_URL}/notifications/channels`);
                setChannels(response.data.filter(c => c.is_active));
            } catch (error) {
                console.error('Error fetching channels:', error);
            }
        };
        if (open) {
            fetchChannels();
        }
    }, [open]);


    useEffect(() => {
        if (item) {
            setFormData({
                url: item.url || '',
                name: item.name || '',
                target_price: item.target_price || '',
                tags: item.tags || '',
                description: item.description || '',
                notification_channel_id: item.notification_channel_id ? item.notification_channel_id.toString() : 'none',
                category: item.category || ''
            });
            setShowCustomInput(!!item.category && !categories.includes(item.category));
        } else {
            setFormData({
                url: '',
                name: '',
                target_price: '',
                tags: '',
                description: '',
                notification_channel_id: 'none',
                category: ''
            });
            setShowCustomInput(false);
        }
    }, [item, open, categories]);



    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const payload = {
                ...formData,
                target_price: formData.target_price ? parseFloat(formData.target_price) : null,
                notification_channel_id: formData.notification_channel_id === 'none' ? null : parseInt(formData.notification_channel_id)
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
                        <Label htmlFor="category">{t('itemModal.category') || 'Category'}</Label>
                        {showCustomInput ? (
                            <div className="flex gap-2">
                                <Input
                                    id="custom_category"
                                    placeholder="Enter new category"
                                    value={formData.category}
                                    onChange={e => setFormData({ ...formData, category: e.target.value })}
                                    autoFocus
                                />
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => {
                                        setShowCustomInput(false);
                                        setFormData({ ...formData, category: '' });
                                    }}
                                    title="Select existing category"
                                >
                                    <X className="h-4 w-4" />
                                </Button>
                            </div>
                        ) : (
                            <Select
                                value={categories.includes(formData.category) ? formData.category : (formData.category ? '__custom__' : 'none')}
                                onValueChange={(val) => {
                                    if (val === '__custom__') {
                                        setShowCustomInput(true);
                                        setFormData({ ...formData, category: '' });
                                    } else if (val === 'none') {
                                        setFormData({ ...formData, category: '' });
                                    } else {
                                        setFormData({ ...formData, category: val });
                                    }
                                }}
                            >
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select a category" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="none">None</SelectItem>
                                    {categories.map(cat => (
                                        <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                                    ))}
                                    <SelectItem value="__custom__">Custom...</SelectItem>
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="channel">Notification Channel</Label>
                        <Select
                            value={formData.notification_channel_id}
                            onValueChange={(val) => setFormData({ ...formData, notification_channel_id: val })}
                        >
                            <SelectTrigger>
                                <SelectValue placeholder="Select a channel" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="none">None</SelectItem>
                                {channels.map(channel => (
                                    <SelectItem key={channel.id} value={channel.id.toString()}>
                                        {channel.name} ({channel.type})
                                    </SelectItem>
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
