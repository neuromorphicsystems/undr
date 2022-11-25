import styled, { keyframes } from "styled-components";

interface SpinnerProps {
    branches: number;
    period: number;
}

const StyledSpinner = styled.div`
    position: relative;
    width: 60px;
    height: 60px;
`;

const spin = keyframes`
    0% {
        opacity: 1;
    }
    100% {
        opacity: 0;
    }
`;

interface BranchProps {
    index: number;
    branches: number;
    period: number;
    side: number;
    thickness: number;
}

const Branch = styled.div<BranchProps>`
    transform: rotate(${props => props.index * 30}deg);
    transform-origin: ${props => props.side}px ${props => props.side}px;
    animation: ${spin} ${props => props.period}s linear infinite;
    animation-delay: ${props =>
        ((props.index - 1 - props.branches) / props.branches) * props.period}s;
    &:after {
        content: "";
        display: block;
        position: absolute;
        top: ${props => props.thickness / 2}px;
        left: ${props => props.side - props.thickness / 2}px;
        width: ${props => props.thickness}px;
        height: ${props => props.side / 2}px;
        border-radius: ${props => props.thickness}px;
        background: ${props => props.theme.content2};
    }
`;

export { StyledSpinner };

export default function Spinner(props: SpinnerProps) {
    return (
        <StyledSpinner>
            {new Array(props.branches).fill(null).map((_, index) => (
                <Branch
                    key={index}
                    index={index}
                    branches={props.branches}
                    period={props.period}
                    side={26}
                    thickness={4}
                />
            ))}
        </StyledSpinner>
    );
}
