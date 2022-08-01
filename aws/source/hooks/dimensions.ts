import * as React from "react";

export interface Dimensions {
    width: number | null;
    height: number | null;
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

export default function useDimensions<Element extends HTMLElement>(): [
    React.RefObject<Element>,
    Dimensions
] {
    const element = React.useRef<Element>(null);
    const [dimensions, setDimensions] = React.useState<Dimensions>({
        width: null,
        height: null,
    });
    React.useEffect(() => {
        if (element.current != null) {
            setDimensions({
                width: element.current.offsetWidth,
                height: element.current.offsetHeight,
            });
        }
        if (element.current == null) {
            throw new Error("unassigned element reference");
        }
        const listener = debounce((event: Event) => {
            setDimensions({
                width: (event as unknown as ResizeObserverSize).inlineSize,
                height: (event as unknown as ResizeObserverSize).blockSize,
            });
        }, 16);
        const observer = new ResizeObserver(entries => {
            for (const entry of entries) {
                listener.handleEvent(
                    entry.borderBoxSize[0] as unknown as Event
                );
            }
        });
        observer.observe(element.current);
        return function cleanup() {
            observer.disconnect();
            listener.reset();
        };
    }, []);
    return [element, dimensions];
}
