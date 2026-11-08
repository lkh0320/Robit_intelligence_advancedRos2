"""인터페이스를 지나는 UDP 패킷을 세고, ping 페이로드(x 반복)가 보이는 패킷을 따로 센다.
페이로드 패킷은 나감/들어옴과 유니캐스트/멀티캐스트로 나눠서 센다.
tcpdump 는 Ubuntu 프로파일 때문에 종료 신호가 막혀서 쓰지 않았다.
SIGTERM 을 받거나 SNIFF_STOP 파일이 생기면 결과를 출력하고 끝낸다.
환경변수: SNIFF_IFACE(기본 lo), SNIFF_STOP
"""
import os
import signal
import socket

ETH_P_ALL = 0x0003
PACKET_OUTGOING = 4
IFACE = os.environ.get('SNIFF_IFACE', 'lo')
STOP = os.environ.get('SNIFF_STOP')
s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
s.bind((IFACE, 0))
s.settimeout(0.2)
print('ready', flush=True)
running = True


def stop(*_):
    global running
    running = False


signal.signal(signal.SIGTERM, stop)
udp = payload = 0
kinds = {'in_uni': 0, 'in_multi': 0, 'out_uni': 0, 'out_multi': 0}
while running and not (STOP and os.path.exists(STOP)):
    try:
        pkt, addr = s.recvfrom(65535)
    except (socket.timeout, InterruptedError):
        continue
    outgoing = addr[2] == PACKET_OUTGOING
    if IFACE == 'lo' and outgoing:  # lo 는 같은 패킷이 나가고 들어오며 두 번 보인다
        continue
    if len(pkt) > 33 and pkt[12:14] == b'\x08\x00' and pkt[23] == 17:
        udp += 1
        if b'x' * 20 in pkt:
            payload += 1
            multi = 224 <= pkt[30] <= 239
            kinds[f"{'out' if outgoing else 'in'}_{'multi' if multi else 'uni'}"] += 1
print(f'UDP 패킷 전체: {udp} / 페이로드가 보인 패킷: {payload}', flush=True)
print(' '.join(f'{k}={v}' for k, v in kinds.items()), flush=True)
