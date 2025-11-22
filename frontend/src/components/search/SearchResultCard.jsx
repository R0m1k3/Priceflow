import React from 'react';
import { ExternalLink, Plus, Package, PackageX } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export function SearchResultCard({ result, onAddToMonitoring }) {
    const formatPrice = (price) => {
        if (price === null || price === undefined) return 'N/A';
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: result.currency || 'EUR',
        }).format(price);
    };

    const truncateTitle = (title, maxLength = 60) => {
        if (!title) return 'Produit sans nom';
        if (title.length <= maxLength) return title;
        return title.substring(0, maxLength) + '...';
    };

    return (
        <Card className="overflow-hidden hover:shadow-lg transition-shadow">
            <CardContent className="p-0">
                {/* Image */}
                <div className="aspect-square bg-muted flex items-center justify-center">
                    {result.image_url ? (
                        <img
                            src={result.image_url}
                            alt={result.title}
                            className="w-full h-full object-contain"
                            onError={(e) => {
                                e.target.style.display = 'none';
                                e.target.nextSibling.style.display = 'flex';
                            }}
                        />
                    ) : null}
                    <div
                        className={`w-full h-full items-center justify-center text-muted-foreground ${result.image_url ? 'hidden' : 'flex'}`}
                    >
                        <Package className="h-16 w-16" />
                    </div>
                </div>

                {/* Content */}
                <div className="p-4 space-y-3">
                    {/* Title */}
                    <h3 className="font-medium text-sm leading-tight line-clamp-2" title={result.title}>
                        {truncateTitle(result.title)}
                    </h3>

                    {/* Price & Stock */}
                    <div className="flex items-center justify-between">
                        <span className="text-xl font-bold text-primary">
                            {formatPrice(result.price)}
                        </span>
                        {result.in_stock !== null && (
                            <Badge
                                variant={result.in_stock ? 'default' : 'destructive'}
                                className="text-xs"
                            >
                                {result.in_stock ? (
                                    <>
                                        <Package className="h-3 w-3 mr-1" />
                                        En stock
                                    </>
                                ) : (
                                    <>
                                        <PackageX className="h-3 w-3 mr-1" />
                                        Rupture
                                    </>
                                )}
                            </Badge>
                        )}
                    </div>

                    {/* Site */}
                    <div className="flex items-center text-xs text-muted-foreground">
                        <span className="truncate">{result.site_name}</span>
                        {result.confidence && (
                            <span className="ml-auto text-xs opacity-50">
                                {Math.round(result.confidence * 100)}%
                            </span>
                        )}
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2 pt-2">
                        <Button
                            variant="default"
                            size="sm"
                            className="flex-1"
                            onClick={onAddToMonitoring}
                        >
                            <Plus className="h-4 w-4 mr-1" />
                            Suivre
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            asChild
                        >
                            <a href={result.url} target="_blank" rel="noopener noreferrer">
                                <ExternalLink className="h-4 w-4" />
                            </a>
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
