interface PanicButtonProps {
    onPanic: () => void;
    disabled?: boolean;
}

export function PanicButton({ onPanic, disabled }: PanicButtonProps) {
    const handleClick = () => {
        if (confirm('⚠️ Bu işlem TÜM açık pozisyonları kapatacak ve botu durduracak. Emin misiniz?')) {
            onPanic();
        }
    };

    return (
        <button
            onClick={handleClick}
            disabled={disabled}
            className="w-full px-6 py-4 bg-red-600 hover:bg-red-700 active:bg-red-800 
                 text-white font-bold text-lg rounded-xl shadow-lg shadow-red-500/30
                 transition-all duration-200 hover:scale-105 active:scale-95
                 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100
                 flex items-center justify-center gap-3"
        >
            <span className="text-2xl">🔴</span>
            <span>PANIC STOP - CLOSE ALL</span>
        </button>
    );
}
