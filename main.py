from socket import socket, AF_INET, SOCK_DGRAM
from threading import Thread
from os.path import basename

import protocol



identifier = 0


def send(packet: protocol.Protocol):
    setIdentifier(packet)
    server.sendto(packet.getFullPacket(), ADDR)



def setIdentifier(packet: protocol.Protocol) -> None:
    packet.setIdentifier(identifier)

    identifier += 1

    if identifier > 0xffff:
        identifier = 0


def closeReciever() -> None:
    while True:
        closeMsg = str(input())

        if closeMsg == "CLOSE CONNECTION":
            print("CLOSING CONNECTION...")
            server.close()
            print("CONNECTION CLOSED")

            return


def msgHandling() -> None:
    
    while True:
        #try except kvoli tomu, ked sa prijimac rozhodne skoncit 
        try:
            msg, addr = server.recvfrom(1024)
        except:
            return
        

        print("sprava prijata")

        protocolFormatMsg = protocol.Protocol()
        protocolFormatMsg.buildFromBytes(msg)
    

        #MSG
        if protocolFormatMsg.getType() == '1':
            if protocolFormatMsg.getData() == "DISCONNECT":
                return

            if protocolFormatMsg.getFrag() == '0':
                print(f"{protocolFormatMsg.getData()} from {addr}")

            elif protocolFormatMsg.getFrag() == '1':
                packets = [protocolFormatMsg]

                while True:
                    msg, addr = server.recvfrom(1024)
                    protocolFormatMsg = protocol.Protocol()
                    protocolFormatMsg.buildFromBytes(msg)

                    packets.append(protocolFormatMsg)

                    if protocolFormatMsg.getFrag() == '3':
                        buildMessage(packets)
                        break



        #FILE
        elif protocolFormatMsg.getType() == '2':
            packets = [protocolFormatMsg]

            while True:
                msg, addr = server.recvfrom(1024)
                protocolFormatMsg = protocol.Protocol()
                protocolFormatMsg.buildFromBytes(msg)

                if protocolFormatMsg.getType() == '3':
                    packets.append(protocolFormatMsg)

                    if protocolFormatMsg.getFrag() == '3':
                        buildFile(packets)
                        break

                else:
                    break



        #ERR
        else:
            print("coska je zle")
            return


        #poslanie ACK naspat odosielatelovi
        ack = protocol.Protocol()
        ack.setType("ACK")
        server.sendto(ack.getFullPacket(), addr)


def fragmentMessage(message: str) -> list[protocol.Protocol]:
    packets = list()
    
    while message:
        temp = message[:fragmentSize]
        message = message[fragmentSize:]

        packet = protocol.Protocol()
        packet.setType("MSG")
        packet.setFrag('2')
        packet.setData(temp)

        packets.append(packet)


    packets[0].setFrag('1')
    packets[-1].setFrag('3')

    return packets

def buildMessage(packets=list[protocol.Protocol]):
    message = ""

    for packet in packets:
        message += packet.getData()

    print(message)


#funkcia fragmentuje subor na mensie casti a vrati vsetky fragmenty 
def fragmentFile(filePath=str) -> list[protocol.Protocol]:
    packets = []

    fileNamePacket = protocol.Protocol()

    fileNamePacket.setType("FILENAME")
    fileNamePacket.setData(basename(filePath))

    packets.append(fileNamePacket)


    with open(filePath, "r", encoding="utf-8") as file:

        while True:
            data = file.read(fragmentSize)
        
            if not data:
                break
        
            packet = protocol.Protocol()
            packet.setType("FILECONTENT")
            packet.setFrag('2')
            packet.setData(data)

            packets.append(packet)

    if len(packets) > 2:
        packets[1].setFrag('1')

    packets[-1].setFrag('3')

    return packets

def buildFile(packets=list[protocol.Protocol]) -> None:
    with open(packets[0].getData(), "w") as file:
        for packet in packets[1:]:
            file.write(packet.getData())


#TODO pridat event na ukoncenie msgHandlingThread
def reciever():
    server.bind(ADDR)

    print(f"Active reciever on {ADDR[0]} on port {ADDR[1]}")

    #na jednom vlakne bezi spravovanie prijimaca, na druhom prijimanie sprav od vysielaca
    msgHandlingThread = Thread(target=msgHandling)
    closeRecieverThread = Thread(target=closeReciever)


    msgHandlingThread.start()
    closeRecieverThread.start()

    msgHandlingThread.join()
    closeRecieverThread.join()


def transmitter():
    msg = protocol.Protocol()
    msg.setType("MSG")
    msg.setFrag('0')
    msg.setData("Hello reciever!")
    server.sendto(msg.getFullPacket(), ADDR)


    while True:
        inputBuffer = str(input())


        if len(inputBuffer) >= 4 and inputBuffer[:4 ] == "FILE":
            inputBuffer = inputBuffer[5:]

            packets = fragmentFile(inputBuffer)

            for packet in packets:
                server.sendto(packet.getFullPacket(), ADDR)


        else:

            if len(inputBuffer) > fragmentSize:
                packets = fragmentMessage(inputBuffer)

                for packet in packets:
                    server.sendto(packet.getFullPacket(), ADDR)

            else:
                packet = protocol.Protocol()
                packet.setType("MSG")
                packet.setFrag('0')
                packet.setData(inputBuffer)

            server.sendto(packet.getFullPacket(), ADDR)


        #_____________ACK zo strany prijimaca______________
        ack, addr = server.recvfrom(1024)
        ackMsg = protocol.Protocol()
        ackMsg.buildFromBytes(ack)


        if inputBuffer == "DISCONNECT":
            break


if __name__ == "__main__":
    commType = input("zadajte typ komunikacie, R - reciever, T - transmitter, K - ukoncit ")

    ip = bytes(input("zadajte IP "), "utf-8")
    port = int(input("zadajte port "))


    ADDR = (ip, port)


    server = socket(AF_INET, SOCK_DGRAM)

    fragmentSize = 4

    if commType == 'R':
        reciever()
    elif commType == 'T':
        transmitter()
    elif commType == 'K':
        exit()
    else:
        print("error")
        exit()