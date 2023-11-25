from socket import socket, AF_INET, SOCK_DGRAM
from threading import Thread, Event
from os.path import basename
from time import sleep
from select import select

import protocol


isReciever = isTransmitter = False

inputBufferQueue = list()

identifier = 0

addr = ()

recieverAddr = ('localhost', 12345)
transmitterAddr = ('localhost', 54321)

switch = True

pathToSaveFile = ''


def send(packet: protocol.Protocol, addr):
    setIdentifier(packet)
    sprava = packet.getFullPacket()
    sock.sendto(sprava, addr)

def setIdentifier(packet: protocol.Protocol) -> None:
    global identifier
    
    packet.setIdentifier(identifier)

    identifier += 1

    if identifier > 0xffff:
        identifier = 0

def checksum(word: str, divisor=0x11021):
    word = int.from_bytes(word.encode("utf-8"), byteorder='big')
    word <<= 16

    while word.bit_length() > 16:

        if word.bit_length() > divisor.bit_length():
            divisor <<= (word.bit_length() - divisor.bit_length())
        else:
            divisor >>= (divisor.bit_length() - word.bit_length())

        word ^= divisor

    return protocol.pack('>H', word)

def fragmentMessage(message: str) -> list[protocol.Protocol]:
    packets = list()
    
    while len(message) > fragmentSize:
        temp = message[:fragmentSize]
        message = message[fragmentSize:]

        packet = protocol.Protocol()
        packet.setType("MSG")
        packet.setFrag("MORE")
        packet.setData(temp)

        packets.append(packet)

    packet = protocol.Protocol()
    packet.setType("MSG")
    packet.setFrag("MORE")
    packet.setData(message)

    packets.append(packet)

    packets[0].setFrag("FIRST")
    packets[-1].setFrag("LAST")

    return packets

def buildMessage(packets: list[protocol.Protocol]):
    message = ""

    for packet in packets:
        message += packet.getData()

    print(message, end='')


#funkcia fragmentuje subor na mensie casti a vrati vsetky fragmenty 
def fragmentFile(filePath: str) -> list[protocol.Protocol]:
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
            packet.setFrag("MORE")
            packet.setData(data)

            packets.append(packet)

    if len(packets) > 2:
        packets[1].setFrag("FIRST")

    packets[-1].setFrag("LAST")

    return packets

def buildFile(packets: list[protocol.Protocol]) -> None:
    global pathToSaveFile

    print("You have recieved a file, please type \"SAVE <path with \\ as delimiter>\" to save the file")

    while not pathToSaveFile:
        sleep(0.5)

    #opravit aby to mohlo byt fragmentovane
    pathToSaveFile += packets[0].getData()
    
    with open(packets[0].getData(), "w") as file:
        for packet in packets[1:]:
            file.write(packet.getData())

    pathToSaveFile = ''


def CLI() -> None:
    global inputBufferQueue, pathToSaveFile

    while True:
        inputBuffer = str(input())

        if inputBuffer == "CLOSE RECIEVER":
            if isReciever:

                print("CLOSING RECIEVER...")
                sock.close()                
                print("RECIEVER CLOSED")

                return

        elif inputBuffer == "CLOSE TRANSMITTER":
            if isTransmitter:
                inputBufferQueue.append(inputBuffer)

                return
            
        elif inputBuffer[:4] == "SAVE" and isReciever:
            pathToSaveFile = inputBuffer[4:] + '\\'
        
        else:
            inputBufferQueue.append(inputBuffer)



def reciever() -> None:
    global sock, addr, recieverAddr, transmitterAddr, identifier, isReciever, isTransmitter, switch

    isReciever = True
    isTransmitter = False
    switch = False

    sock = socket(AF_INET, SOCK_DGRAM)
    sock.settimeout(5)
    sock.bind(recieverAddr)


    print(f"Active reciever on {recieverAddr[0]} on port {recieverAddr[1]}")

    while True:
        #try except kvoli tomu, ked sa prijimac rozhodne skoncit 

        for _ in range(5):
            try:
                msg, transmitterAddr = sock.recvfrom(1024)
                break
            except (TimeoutError, ConnectionResetError):
                continue
            except OSError:
                return
        
        else:
            print("No message recieved from transmitter, if you wish not to continue type CLOSE RECIEVER")
            continue


        protocolFormatMsg = protocol.Protocol()
        protocolFormatMsg.buildFromBytes(msg)

        
    
        #TRANSMITTER CLOSED
        if protocolFormatMsg.getType() == "CLOSE":
            print(f"TRANSMITTER on {transmitterAddr} was closed. \n If you wish to close reciever, type \"CLOSE RECIEVER\"")
            
            acceptClose = protocol.Protocol()
            acceptClose.setType("CLOSE")
            
            send(acceptClose, transmitterAddr)


            continue

        #SWITCH
        elif protocolFormatMsg.getType() == "SWITCH":
            print(f"TRANSMITTER on {transmitterAddr} initialized switch.")

            acceptSwitch = protocol.Protocol()
            acceptSwitch.setType("SWITCH")
            
            send(acceptSwitch, transmitterAddr)

            #TODO zmena adries a portov + vynulovanie identifier 
            identifier = 0
            recieverAddr, transmitterAddr = transmitterAddr, recieverAddr

            sock.close()

            switch = True
            return

        #RemainConnection
        elif protocolFormatMsg.getType() == "REMAIN CONNECTION":
            print("REMAIN CONNECTION")

            remainConnction = protocol.Protocol()
            remainConnction.setType("REMAIN CONNECTION")

            send(remainConnction, transmitterAddr)

            continue


        #MSG
        elif protocolFormatMsg.getType() == "MSG":

            #kontrola checksum, ak nesedi, tak posle nAck a transmitter posle znova
            if protocolFormatMsg.getChecksum() != checksum(protocolFormatMsg.getData()):
                print("bad checksum")
                continue
    
            if protocolFormatMsg.getFrag() == "NO":
                print(f"{protocolFormatMsg.getData()} from {transmitterAddr}")

            elif protocolFormatMsg.getFrag() == "FIRST":
                packets = [protocolFormatMsg]

                while True:
                    msg, transmitterAddr = sock.recvfrom(1024)
                    protocolFormatMsg = protocol.Protocol()
                    protocolFormatMsg.buildFromBytes(msg)

                    if protocolFormatMsg.getFrag() == "MORE":
                        packets.append(protocolFormatMsg)

                    if protocolFormatMsg.getFrag() == "LAST":
                        packets.append(protocolFormatMsg)

                        buildMessage(packets)
                        
                        print(f" from {transmitterAddr}")
                        break



        #FILE
        elif protocolFormatMsg.getType() == "FILENAME":
            packets = [protocolFormatMsg]

            while True:
                msg, transmitterAddr = sock.recvfrom(1024)
                protocolFormatMsg = protocol.Protocol()
                protocolFormatMsg.buildFromBytes(msg)

                if protocolFormatMsg.getType() == "FILECONTENT":
                    packets.append(protocolFormatMsg)

                    if protocolFormatMsg.getFrag() == "LAST":
                        buildFile(packets)
                        break

                else:
                    break

        else:
            print("ERROR")
            return


def transmitter() -> None:
    global sock, addr, recieverAddr, transmitterAddr, identifier, isReciever, isTransmitter, switch 

    isReciever = False
    isTransmitter = True
    switch = False

    sock = socket(AF_INET, SOCK_DGRAM)
    sock.settimeout(10) #momentalne je to 10 sekund, ale to sa vsetko zmeni ked pribudne ARQ
    sock.bind(transmitterAddr)

    print(f"Active transmitter on {transmitterAddr[0]} on port {transmitterAddr[1]}")


    while True:
        inputBuffer = None

        #po dobu 5 sekund sa snazi nieco poslat, ak to nepojde, tak posle RemainConneciton packet
        for _ in range(10):
            try:
                inputBuffer = inputBufferQueue.pop()
                break
            except:
                sleep(0.5)


        if inputBuffer:
            #ukoncenie TRANSMITTERa
            if inputBuffer == "CLOSE TRANSMITTER":
                
                packet = protocol.Protocol()
                packet.setType("CLOSE")

                send(packet, recieverAddr)

                #prijatie CLOSE spravy / potvrdenie CLOSE od RECIEVERa
                sock.settimeout(5)
                for _ in range(3):
                    try:
                        closePacket, recieverAddr = sock.recvfrom(1024)
                        break
                    except (TimeoutError, ConnectionResetError):
                        continue
                
                else:
                    sock.settimeout(None)
                    print("TRANSMITTER succesfully closed") 
                    print("RECIEVER didnt sent ACK")
                    return 


                sock.settimeout(None)

                close = protocol.Protocol()
                close.buildFromBytes(closePacket)

                if close.getType() == "CLOSE":
                    print("TRANSMITTER succesfully closed") 
                    return

                else:
                    print("ERROR")
                    return
                


            #vymena TRANSMITTER a RECIEVER
            elif inputBuffer == "SWITCH":
                packet = protocol.Protocol()
                packet.setType("SWITCH")

                send(packet, recieverAddr)

                #prijatie CLOSE spravy / potvrdenie CLOSE od RECIEVERa
                sock.settimeout(5)
                for _ in range(3):
                    try:
                        switchPacket, recieverAddr = sock.recvfrom(1024)
                        break
                    except (TimeoutError, ConnectionResetError):
                        continue
                
                else:
                    print("RECIEVER did not accept SWITCH")
                    return

                sock.settimeout(None)

                switch = protocol.Protocol()
                switch.buildFromBytes(switchPacket)

                if switch.getType() == "SWITCH":
                    print("TRANSMITTER and RECIEVER succesfully switched") 

                    #TODO zmena adresy, portu + vynulovanie identifier
                    identifier = 0
                    recieverAddr, transmitterAddr = transmitterAddr, recieverAddr
                    
                    sock.close()
                    switch = True

                    return

                else:
                    print("Error - wrong ACK recieved")
                    return




            elif len(inputBuffer) >= 4 and inputBuffer[:4 ] == "FILE":
                inputBuffer = inputBuffer[5:]

                packets = fragmentFile(inputBuffer)

                for packet in packets:
                    send(packet, recieverAddr)


            else:
                if len(inputBuffer) > fragmentSize:
                    packets = fragmentMessage(inputBuffer)

                    for packet in packets:
                        send(packet, recieverAddr)

                else:
                    packet = protocol.Protocol()
                    packet.setType("MSG")
                    packet.setFrag("NO")
                    packet.setData(inputBuffer)

                    send(packet, recieverAddr)


        #REMAIN CONNECTION - ak sa 5 sekund neodosle sprava, tak sa posle REMAIN CONNECTION packet, ak na neho pride odpoved, tak cely tento cyklus zacne od znova, ak ale nepride odpoved, tak sa este 2x skusi poslat REMAIN CONNECTION a ak ani na jeden nedostane odpoved, mozeme povazovat komunikaciu za uzavretu a preto sa TRANSMITTER ukonci
        else:
            packet = protocol.Protocol()
            packet.setType("REMAIN CONNECTION")


            #prijatie CLOSE spravy / potvrdenie CLOSE od RECIEVERa
            sock.settimeout(5)

            for _ in range(3):
                send(packet, recieverAddr)
                
                try:
                    remainConnecitonPacket, recieverAddr = sock.recvfrom(1024)
                    print("Checking for connection")
                    break
                except (TimeoutError, ConnectionResetError):
                    continue
            
            else:
                print("Could not reach, type CLOSE TRANSMITTER to close the transmitter")
                return 


            sock.settimeout(None)
            remainConneciton = protocol.Protocol()
            remainConneciton.buildFromBytes(remainConnecitonPacket)

            if remainConneciton.getType() == "REMAIN CONNECTION":
                print("Connection was maintained") 
                
                continue

            else:
                print("Error - wrong ACK recieved")
                return






if __name__ == "__main__":
    commType = input("R - RECIEVER, T - TRANSMITTER, K - KILL ")

    """ip = bytes(input("IP: "), "utf-8")
    port = int(input("PORT: "))
    fragmentSize = int(input("Select fragment size: "))"""

    fragmentSize = 4


    addr = ("localhost", 12345)

    sock = socket(AF_INET, SOCK_DGRAM)

    cli = Thread(target=CLI)
    cli.start()

    node = ''
    

    while switch:
        if commType == 'R':
            node = Thread(target=reciever)
        elif commType == 'T':
            node = Thread(target=transmitter)
        elif commType == 'K':
            break
        else:
            print("error")
            break

        node.start()
        node.join()

        if switch and type(switch) == bool:
            commType = 'R' if commType == 'T' else 'T'
            

    cli.join()