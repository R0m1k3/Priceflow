import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { X, TrendingDown, TrendingUp, Minus } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

const API_URL = '/api';

export function PriceHistoryModal({ open, onClose, item }) {
    const [priceHistory, setPriceHistory] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (open && item) {
            loadPriceHistory();
        }
    }, [open, item]);

    const loadPriceHistory = async () => {
        if (!item) return;

        setLoading(true);
        try {
            const response = await axios.get(`${API_URL}/items/${item.id}/price-history`);
            setPriceHistory(response.data);
        } catch (error) {
            console.error('Error loading price history:', error);
        } finally {
            setLoading(false);
        }
    };

    if (!item) return null;

    // Calculate stats
    const prices = priceHistory.map(h => h.price);
    const currentPrice = prices[prices.length - 1];
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const avgPrice = prices.length > 0 ? prices.reduce((a, b) => a + b, 0) / prices.length : 0;

    // Calculate price change
    const priceChange = prices.length > 1 ? ((currentPrice - prices[0]) / prices[0] * 100) : 0;

    // Simple chart rendering
    const chartHeight = 200;
    const chartWidth = 600;
    const padding = 40;

    const renderChart = () => {
        if (prices.length === 0) return null;

        const minY = minPrice * 0.95;
        const maxY = maxPrice * 1.05;
        const rangeY = maxY - minY;

        const points = priceHistory.map((point, index) => {
            const x = padding + (index / (priceHistory.length - 1 || 1)) * (chartWidth - 2 * padding);
            const y = chartHeight - padding - ((point.price - minY) / rangeY) * (chartHeight - 2 * padding);
            return { x, y, price: point.price, date: point.timestamp };
        });

        const pathData = points.map((point, index) =>
            `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`
        ).join(' ');

        return (
            <svg width="100%" height={chartHeight} viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="mt-4">
                {/* Grid lines */}
                {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                    const y = padding + ratio * (chartHeight - 2 * padding);
                    const price = maxY - ratio * rangeY;
                    return (
                        <g key={ratio}>
                            <line
                                x1={padding}
                                y1={y}
                                x2={chartWidth - padding}
                                y2={y}
                                stroke="currentColor"
                                strokeOpacity="0.1"
                            />
                            <text x={10} y={y + 4} fontSize="10" fill="currentColor" opacity="0.5">
                                {price.toFixed(2)}€
                            </text>
                        </g>
                    );
                })}

                {/* Area under curve */}
                <path
                    d={`${pathData} L ${points[points.length - 1].x} ${chartHeight - padding} L ${points[0].x} ${chartHeight - padding} Z`}
                    fill="currentColor"
                    fillOpacity="0.1"
                />

                {/* Line */}
                <path
                    d={pathData}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-primary"
                />

                {/* Points */}
                {points.map((point, index) => (
                    <g key={index}>
                        <circle
                            cx={point.x}
                            cy={point.y}
                            r="4"
                            fill="currentColor"
                            className="text-primary"
                        />
                        <title>{`${new Date(point.date).toLocaleDateString('fr-FR')}: ${point.price.toFixed(2)}€`}</title>
                    </g>
                ))}
            </svg>
        );
    };

    return (
        <Dialog open={open} onOpenChange={onClose}>
            <DialogContent className="max-w-3xl">
                <DialogHeader>
                    <DialogTitle>Historique des prix</DialogTitle>
                </DialogHeader>

                <div className="space-y-4">
                    {/* Product Info */}
                    <div>
                        <h3 className="font-semibold line-clamp-2">{item.name}</h3>
                        <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-muted-foreground hover:text-primary"
                        >
                            {new URL(item.url).hostname.replace('www.', '')}
                        </a>
                    </div>

                    {/* Stats Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <Card className="p-3">
                            <div className="text-xs text-muted-foreground">Prix actuel</div>
                            <div className="text-lg font-bold">{currentPrice?.toFixed(2) || '--'}€</div>
                        </Card>
                        <Card className="p-3">
                            <div className="text-xs text-muted-foreground">Prix minimum</div>
                            <div className="text-lg font-bold text-green-600">{minPrice?.toFixed(2) || '--'}€</div>
                        </Card>
                        <Card className="p-3">
                            <div className="text-xs text-muted-foreground">Prix maximum</div>
                            <div className="text-lg font-bold text-red-600">{maxPrice?.toFixed(2) || '--'}€</div>
                        </Card>
                        <Card className="p-3">
                            <div className="text-xs text-muted-foreground">Variation</div>
                            <div className={`text-lg font-bold flex items-center gap-1 ${priceChange > 0 ? 'text-red-600' : priceChange < 0 ? 'text-green-600' : ''}`}>
                                {priceChange > 0 && <TrendingUp className="h-4 w-4" />}
                                {priceChange < 0 && <TrendingDown className="h-4 w-4" />}
                                {priceChange === 0 && <Minus className="h-4 w-4" />}
                                {Math.abs(priceChange).toFixed(1)}%
                            </div>
                        </Card>
                    </div>

                    {/* Chart */}
                    {loading ? (
                        <div className="flex items-center justify-center h-[200px]">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                        </div>
                    ) : priceHistory.length > 0 ? (
                        <div>
                            {renderChart()}
                        </div>
                    ) : (
                        <div className="text-center py-8 text-muted-foreground">
                            Aucun historique de prix disponible
                        </div>
                    )}

                    {/* History Table */}
                    {priceHistory.length > 0 && (
                        <div className="max-h-[200px] overflow-y-auto">
                            <table className="w-full text-sm">
                                <thead className="sticky top-0 bg-background border-b">
                                    <tr>
                                        <th className="text-left p-2">Date</th>
                                        <th className="text-right p-2">Prix</th>
                                        <th className="text-right p-2">Variation</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {priceHistory.map((entry, index) => {
                                        const prevPrice = index > 0 ? priceHistory[index - 1].price : entry.price;
                                        const change = ((entry.price - prevPrice) / prevPrice * 100);
                                        return (
                                            <tr key={index} className="border-b">
                                                <td className="p-2">
                                                    {new Date(entry.timestamp).toLocaleString('fr-FR')}
                                                </td>
                                                <td className="text-right p-2 font-medium">
                                                    {entry.price.toFixed(2)}€
                                                </td>
                                                <td className={`text-right p-2 ${change > 0 ? 'text-red-600' : change < 0 ? 'text-green-600' : ''}`}>
                                                    {change !== 0 ? `${change > 0 ? '+' : ''}${change.toFixed(1)}%` : '-'}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}
