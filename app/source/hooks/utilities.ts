export function clamp(value: number, lowerBound: number, upperBound: number) {
    return Math.min(Math.max(value, lowerBound), upperBound);
}

export function unitClamp(value: number) {
    return Math.min(Math.max(value, 0), 1);
}

export function decimalPlaces(value: number) {
    if (Number.isInteger(value)) {
        return 0;
    }
    return (value.toString().split(".")[1] as string).length;
}

export function durationToString(duration: number) {
    if (duration < 180) {
        return `${duration} s`;
    }
    if (duration < 10800) {
        return `${Math.ceil(duration / 60)} min`;
    }
    if (duration < 259200) {
        return `${Math.ceil(duration / 3600)} h`;
    }
    return `${Math.ceil(duration / 86400)} days`;
}

export function sizeToString(size: bigint) {
    if (size < 1e3) {
        return `${size} B`;
    }
    if (Math.round(Number(size) / 1e1) < 1e5) {
        return `${(Number(size) / 1e3).toFixed(2)} kB`;
    }
    if (Math.round(Number(size) / 1e4) < 1e5) {
        return `${(Number(size) / 1e6).toFixed(2)} MB`;
    }
    if (Math.round(Number(size) / 1e7) < 1e5) {
        return `${(Number(size) / 1e9).toFixed(2)} GB`;
    }
    if (Math.round(Number(size) / 1e10) < 1e5) {
        return `${(Number(size) / 1e12).toFixed(2)} TB`;
    }
    return `${(Number(size) / 1e15).toFixed(2)} PB`;
}

export function speedToString(speed: number) {
    if (speed < 1e3) {
        return `${speed} B/s`;
    }
    if (Math.round(Number(speed) / 1e1) < 1e5) {
        return `${(Number(speed) / 1e3).toFixed(2)} kB/s`;
    }
    if (Math.round(Number(speed) / 1e4) < 1e5) {
        return `${(Number(speed) / 1e6).toFixed(2)} MB/s`;
    }
    if (Math.round(Number(speed) / 1e7) < 1e5) {
        return `${(Number(speed) / 1e9).toFixed(2)} GB/s`;
    }
    if (Math.round(Number(speed) / 1e10) < 1e5) {
        return `${(Number(speed) / 1e12).toFixed(2)} TB/s`;
    }
    return `${(Number(speed) / 1e15).toFixed(2)} PB/s`;
}

export function numberToIntegerWithCommas(value: number) {
    return (
        value
            .toFixed(0)
            .split("")
            .reverse()
            .join("")
            .match(/\d{1,3}/g) as [string]
    )
        .join(",")
        .split("")
        .reverse()
        .join("");
}

export class Listener implements EventListenerObject {
    shouldDispatch: boolean;
    event: Event | null;
    timeout: ReturnType<typeof setTimeout> | null;
    callback: (event: Event) => void;
    delay: number;

    constructor(callback: (event: Event) => void, delay: number) {
        this.shouldDispatch = false;
        this.event = null;
        this.timeout = null;
        this.callback = callback;
        this.delay = delay;
    }

    handleEvent(event: Event) {
        this.event = event;
        this.shouldDispatch = true;
        if (this.timeout == null) {
            this.dispatch();
        }
    }

    dispatch() {
        if (this.shouldDispatch) {
            this.callback(this.event as Event);
            this.shouldDispatch = false;
            this.event = null;
            this.timeout = setTimeout(() => this.dispatch(), this.delay);
        } else {
            this.timeout = null;
        }
    }

    reset() {
        this.shouldDispatch = false;
        this.event = null;
        if (this.timeout != null) {
            clearTimeout(this.timeout);
            this.timeout = null;
        }
    }
}

export function debounce(callback: (event: Event) => void, delay: number) {
    return new Listener(callback, delay);
}

export function sliceEllipsis(items: string[], collapseThreshold: number) {
    if (items.length < collapseThreshold) {
        return items.join(", ");
    }
    return [
        ...items.slice(0, collapseThreshold - 3),
        `... (${items.length - (collapseThreshold - 2)} more)`,
        items[items.length - 1],
    ].join(", ");
}
