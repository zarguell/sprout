function taskIcon(type) {
    return { water: '\uD83D\uDCA7', fertilize: '\uD83E\uDDEA', repot: '\uD83E\uDEB4', custom: '\uD83D\uDCCB' }[type] || '\uD83D\uDCCB';
}

function recurrenceLabel(days) {
    if (days === 7) return 'Weekly';
    if (days === 14) return 'Biweekly';
    if (days === 30) return 'Monthly';
    return 'Every ' + days + ' days';
}

function overdueBadgeClass(days) {
    return days >= 3
        ? 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300'
        : 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300';
}
