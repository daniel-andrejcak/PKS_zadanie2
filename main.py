from socket import socket, AF_INET, SOCK_DGRAM
from threading import Thread, Event
from os.path import basename
from time import sleep
from select import select

import protocol


WINDOWSIZE = 4

isReciever = isTransmitter = False

inputBufferQueue = list()

identifier = 0
notRecievedArray = []

addr = ()

recieverAddr = ('localhost', 12345)
transmitterAddr = ('localhost', 54321)

switchFlag = True

pathToSaveFile = ''


def send(packet: protocol.Protocol, addr):
    setIdentifier(packet)
    sprava = packet.getFullPacket()
    sock.sendto(sprava, addr)
    

def setIdentifier(packet: protocol.Protocol) -> None:
    global identifier

    if packet.getIdentifier() != 0:
        return 


    identifier += 1

    if identifier > 0xffff:
        identifier = 1

    packet.setIdentifier(identifier)

def checksum(packet: protocol.Protocol, divisor=0x11021) -> bool:
    word = packet.getData()
    word = int.from_bytes(word, byteorder='big')
    word <<= 16

    while word.bit_length() > 16:

        if word.bit_length() > divisor.bit_length():
            divisor <<= (word.bit_length() - divisor.bit_length())
        else:
            divisor >>= (divisor.bit_length() - word.bit_length())

        word ^= divisor

    word = protocol.pack('>H', word)

    return packet.getChecksum() == word



def fragmentMessage(message: bytes) -> list[protocol.Protocol]:
    packets = list()
    
    while message:
        temp = message[:fragmentSize]
        message = message[fragmentSize:]

        packet = protocol.Protocol()
        packet.setType("MSG")
        packet.setFrag("MORE")
        packet.setData(temp)
        
        packets.append(packet)


    packets[0].setFrag("FIRST")
    packets[-1].setFrag("LAST")

    return packets

def buildMessage(packets: list[protocol.Protocol]):
    message = b""

    for packet in packets:
        message += packet.getData()

    print(message.decode("utf-8"), end=' ')
    print(f"{len(packets)} fragments, total size {sum(len(packet.getData()) for packet in packets)} B from {transmitterAddr}")



#funkcia fragmentuje subor na mensie casti a vrati vsetky fragmenty 
def fragmentFile(filePath: str) -> list[protocol.Protocol]:
    packets = []

    fileNamePacket = protocol.Protocol()

    fileNamePacket.setType("FILENAME")
    fileNamePacket.setData(basename(filePath).encode("utf-8"))

    packets.append(fileNamePacket)


    with open(filePath, "r", encoding="utf-8") as file:

        while True:
            data = file.read(fragmentSize)
        
            if not data:
                break
        
            packet = protocol.Protocol()
            packet.setType("FILECONTENT")
            packet.setFrag("MORE")
            packet.setData(data.encode("utf-8"))

            packets.append(packet)

    if len(packets) > 2:
        packets[1].setFrag("FIRST")

    packets[-1].setFrag("LAST")

    return packets

def buildFile(packets: list[protocol.Protocol], fileName: str) -> None:
    global pathToSaveFile


    fileNamePackets = filter(lambda packet: packet.getType() == "FILENAME", packets)
    packets = filter(lambda packet: packet.getType() == "FILECONTENT", packets)


    print("You have recieved a file, please type \"SAVE <path with \\ as delimiter>\" to save the file")

    while not pathToSaveFile:
        sleep(0.5)



    pathToSaveFile += buildFileName(fileNamePackets)
    
    with open(pathToSaveFile, "w") as file:
        for packet in packets:
            file.write(packet.getData().decode("utf-8"))

    pathToSaveFile = ''

def buildFileName(packets: list[protocol.Protocol()]) -> str:
    
    fileName = ''

    for packet in packets:
        fileName += packet.getData().decode("utf-8")
    
    return fileName

#pri RECIEVER funguje identifier ako posledny korektne prijaty packet
def checkIntegrity(packet: protocol.Protocol()):
    global identifier, transmitterAddr, notRecievedArray

    
    if checksum(packet):
        ack = protocol.Protocol()
        ack.setType("ACK")
        ack.setIdentifier(packet.getIdentifier())

        sock.sendto(ack.getFullPacket(), transmitterAddr)

        return True
    
    else:
        ack = protocol.Protocol()
        ack.setType("ERR")
        ack.setIdentifier(packet.getIdentifier())

        print(f"Wrong checksum on packet {packet.getIdentifier()}")

        sock.sendto(ack.getFullPacket(), transmitterAddr)

        return False
    
    
    
    
    
    if packet.getIdentifier() in notRecievedArray:
        return

    isCorrect = (identifier + 1) == packet.getIdentifier()


    sock.sendto(ack.getFullPacket(), transmitterAddr)

    if isCorrect:
        identifier = packet.getIdentifier()
        return True





    """# na chybajuce packety posle notAck, tieto ID prida do notRecievedArray, kvoli naslednej kontrole
    if not isCorrect:
        for i in range(identifier + 1, packet.getIdentifier()):
            notAck = protocol.Protocol()
            notAck.setType("ERR")
            notAck.setIdentifier(i)

            sock.sendto(notAck.getFullPacket(), transmitterAddr)

            notRecievedArray.append(i)
        
        return False"""



def ARQ(packets: list[protocol.Protocol], addr, simulate=False) -> None:
    global sock

    sentPacketsQueue = []
    packetsToResend = []
    ackPacket = None
    badPacket = protocol.Protocol()


    windowSize = 4 if len(packets) >= 4 else len(packets)

    
    sendAgain = False

    if simulate:
        packets[-1].checksum = b'\x00\x01'
        badPacket = packets[-1]
        simulate = False
        sendAgain = True
    
    
    
    while packets or packetsToResend:

        if len(packets) < 6:
            pass

        while len(sentPacketsQueue) < windowSize and (packets or packetsToResend):
            if packetsToResend:
                packet = packetsToResend.pop(0)
            else:
                packet = packets.pop(0)

            send(packet, addr)

            if packet == badPacket:
                packet.setChecksum()

            sentPacketsQueue.append(packet)



        currentWindowSize = len(sentPacketsQueue)

        for _ in range(currentWindowSize):
            ackPacket = None

            #packet = sentPacketsQueue.pop(0)
            
            if not ackPacket: 
                try:
                    ackPacket, recieverAddr = sock.recvfrom(1024)
                    ack = protocol.Protocol()
                    ack.buildFromBytes(ackPacket)
                except (TimeoutError, ConnectionResetError):
                    packetsToResend.append(packet)
                    continue
            
            
            #while sentPacketsQueue:
            packet = sentPacketsQueue.pop(0)




            #ak pride spravny ACK
            if packet.getIdentifier() == ack.getIdentifier():
                if ack.getType() == "ACK":
                    print("spravne dorucene - prisiel ACK na jeden fragment")

                elif ack.getType() == "ERR":
                    if sendAgain:
                        packet.setChecksum()
                        sendAgain = False
                
                    packetsToResend.append(packet) 
                    print("nespravne dorucene - checksum nesedi")
            
    

def insertToPacketGroup(packets, packet):
    if packets and packets[-1].getIdentifier() > packet.getIdentifier() + WINDOWSIZE:
        return False
    else:
        packets.append(packet)
        return True    


def insertToPacketArray(packets, packet):
    for packetGroup in packets:
        if insertToPacketGroup(packetGroup, packet):
            return
    else:
        packets.append([packet])



def recieveFragments(initialPacket: protocol.Protocol()):
    
    isComplete = [False, False]
    packets = [[]]

    packetGroup = 0


    firstPacket = protocol.Protocol()
    lastPacket = protocol.Protocol()


    if checkIntegrity(initialPacket):
        packets[0].append(initialPacket)

        if initialPacket.getFrag() == "FIRST":
            isComplete[0] = True
            firstPacket = initialPacket

        elif initialPacket.getFrag() == "LAST":
            isComplete[1] = True
            lastPacket = initialPacket

    while True:

        try:
            packet, transmitterAddr = sock.recvfrom(1024)
        except (TimeoutError, ConnectionResetError):
            continue
        except OSError:
            return
        
        
        protocolFormatPacket = protocol.Protocol()
        protocolFormatPacket.buildFromBytes(packet)


        if not checkIntegrity(protocolFormatPacket):
            continue

        
        insertToPacketArray(packets, protocolFormatPacket)




        if protocolFormatPacket.getFrag() == "FIRST" and not isComplete[0]:
            isComplete[0] = True
            firstPacket = protocolFormatPacket
            
        elif protocolFormatPacket.getFrag() == "LAST" and not isComplete[1]:
            isComplete[1] = True
            lastPacket = protocolFormatPacket
            break #toto je len docasne riesenie

        


        #vsetky packety boli prijate
        if lastPacket.getIdentifier() != 0 and lastPacket.getIdentifier() + ((len(packets) - 1) * 0xffff) - firstPacket.getIdentifier() + 1 == packetArrayLen(packets):
            break


    
    for packetGroup in packets:
        packetGroup = sorted(packetGroup, key=lambda packet: packet.getIdentifier())


    packets = [packet for packetGroup in packets for packet in packetGroup]


    if all([packet.getType() == "MSG" for packet in packets]):
        buildMessage(packets)

    elif all([packet.getType() == "FILENAME" or packet.getType() == "FILECONTENT" for packet in packets]):
        buildFile(packets)
        



def packetArrayLen(packets: list) -> int :
    return sum(len(packetGroup) for packetGroup in packets)

    

def CLI() -> None:
    global inputBufferQueue, pathToSaveFile, fragmentSize

    while True:
        inputBuffer = str(input())

        if isReciever:
            if inputBuffer == "CLOSE RECIEVER":
                if isReciever:

                    print("CLOSING RECIEVER...")
                    sock.close()                
                    print("RECIEVER CLOSED")

                    return
            
            elif inputBuffer[:4] == "SAVE" and isReciever:
                pathToSaveFile = inputBuffer[5:]


        elif isTransmitter:
            if inputBuffer == "CLOSE TRANSMITTER":
                if isTransmitter:
                    inputBufferQueue.append(inputBuffer)

                    return
                
            
            elif inputBuffer[:9] == "FRAG SIZE":
                fragmentSize = int(inputBuffer[9:])


            elif inputBuffer == "SIMULATE ERROR":
                simulateError()

            else:
                inputBufferQueue.append(inputBuffer)



def reciever() -> None:
    global isReciever, isTransmitter, switchFlag, sock, addr, recieverAddr, transmitterAddr, identifier

    #nastavenie bool hodnot, pre pouzitie CLI, pripadny SWITCH
    isReciever = True
    isTransmitter = False
    switchFlag = False

    #vytvorenie socketu na ktorom pracuje
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

    
        #___________TRANSMITTER CLOSED__________
        if protocolFormatMsg.getType() == "CLOSE":

            print(f"TRANSMITTER on {transmitterAddr} was closed. \n If you wish to close reciever, type \"CLOSE RECIEVER\"")
            
            closeAck = protocol.Protocol()
            closeAck.setType("CLOSE")
            
            sock.sendto(closeAck.getFullPacket(), transmitterAddr)



        #______________SWITCH______________
        elif protocolFormatMsg.getType() == "SWITCH":

            print(f"TRANSMITTER on {transmitterAddr} initialized switch.")

            switchAck = protocol.Protocol()
            switchAck.setType("SWITCH")
            
            sock.sendto(switchAck.getFullPacket(), transmitterAddr)

            #TODO zmena adries a portov + vynulovanie identifier 
            identifier = 0
            recieverAddr, transmitterAddr = transmitterAddr, recieverAddr

            sock.close()

            switchFlag = True
            return



        #________REMAIN CONNECTION_________
        #ak prijeme spravu REMAIN CONNECTION, tak naspat posle taku istu spravu - to sluzi ako ACK pre TRANSMITTER
        elif protocolFormatMsg.getType() == "REMAIN CONNECTION":

            #print("REMAIN CONNECTION message recieved, sending ACK...")

            remainConnctionAck = protocol.Protocol()
            remainConnctionAck.setType("REMAIN CONNECTION")

            sock.sendto(remainConnctionAck.getFullPacket(), transmitterAddr)



        #MSG
        elif protocolFormatMsg.getType() == "MSG":

            if protocolFormatMsg.getFrag() == "NO":
                if checkIntegrity(protocolFormatMsg):
                    print(f"{protocolFormatMsg.getData().decode('utf-8')} from {transmitterAddr}")

            else:
                recieveFragments(protocolFormatMsg)




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



        #ak dostane nejaky neznamy type - poskodena sprava
        else:
            print("Error - wrong type of packet recieved")
            continue



def transmitter() -> None:
    global isReciever, isTransmitter, switchFlag, sock, addr, recieverAddr, transmitterAddr, identifier 

    #nastavenie bool hodnot, pre pouzitie CLI, pripadny SWITCH
    isReciever = False
    isTransmitter = True
    switchFlag = False

    #vytvorenie socketu na ktorom pracuje
    sock = socket(AF_INET, SOCK_DGRAM)
    sock.bind(transmitterAddr)

    print(f"Active transmitter on {transmitterAddr[0]} on port {transmitterAddr[1]}")


    while True:

        #po dobu 5 sekund sa snazi nieco poslat, ak to nepojde, tak posle RemainConneciton packet
        inputBuffer = None
        for _ in range(1000):
            try:
                inputBuffer = inputBufferQueue.pop(0)
                break

            except:
                sleep(0.5)



        if inputBuffer:
            #ukoncenie TRANSMITTERa
            #posle spravu o vypnuti RECIEVEROVI a caka na odpoved - idealna situacia
            #ak odpoved nepride, tak to zopakuje este 2x kazdych 5 sekund, ak pride odpoved, tak ^
            #ak ani potom nepride odpoved, tak sa vypne, ale oznami, ze RECIEVER nedostal spravu o ukonceni
            if inputBuffer == "CLOSE TRANSMITTER":
                
                close = protocol.Protocol()
                close.setType("CLOSE")

                #poslanie CLOSE spravy

                #prijatie CLOSE spravy - potvrdenie CLOSE od RECIEVERa
                sock.settimeout(5)

                for _ in range(3):
                    sock.sendto(close.getFullPacket(), recieverAddr)
                    
                    try:
                        closeAckPacket, recieverAddr = sock.recvfrom(1024)
                        break
                    except (TimeoutError, ConnectionResetError):
                        continue
                
                else:
                    print("TRANSMITTER succesfully closed") 
                    print("RECIEVER didnt sent ACK")
                    return 


                closeAck = protocol.Protocol()
                closeAck.buildFromBytes(closeAckPacket)

                if closeAck.getType() == "CLOSE":
                    print("TRANSMITTER succesfully closed") 
                    return

                else:
                    print("Error - wrong CLOSE recieved")
                    return



            #vymena TRANSMITTER a RECIEVER
            #TRANSMITTER posle spravu SWITCH, RECIEVER dostane tuto spravu, posle odpoved, vymenia sa - idealna situacia
            #ak nedostane odpoved, posle este 3x kazdych 5sek, ak dostane odpoved ^
            #ak nedostane odpoved, tak napise spravu ze nic z toho a klasicky pokracuje dalej
            elif inputBuffer == "SWITCH":

                switch = protocol.Protocol()
                switch.setType("SWITCH")


                sock.settimeout(5)

                for _ in range(3):
                    sock.sendto(switch.getFullPacket(), recieverAddr)

                    try:
                        #prijatie SWITCH spravy - potvrdenie SWITCH od RECIEVERa
                        switchAckPacket, recieverAddr = sock.recvfrom(1024)
                        break
                    except (TimeoutError, ConnectionResetError):
                        continue
                
                else:
                    print("RECIEVER did not accept SWITCH.\nIf you want to close transmitter, type CLOSE TRANSMITTER.\nIf not, you can continue using the transmitter")
                    continue



                switchAck = protocol.Protocol()
                switchAck.buildFromBytes(switchAckPacket)

                if switchAck.getType() == "SWITCH":
                    print("TRANSMITTER and RECIEVER succesfully switched") 

                    #zmena adresy, portu + vynulovanie identifier
                    identifier = 0
                    recieverAddr, transmitterAddr = transmitterAddr, recieverAddr
                    
                    sock.close()
                    switchFlag = True

                    return

                else:
                    print("Error - wrong SWITCH recieved")
                    return



            #__________SENDING FILE_____________
            elif len(inputBuffer) >= 4 and inputBuffer[:4 ] == "FILE":
                inputBuffer = inputBuffer[5:]

                packets = fragmentFile(inputBuffer)

                for packet in packets:
                    send(packet, recieverAddr)



            #__________SENDING MESSAGE__________
            else:

                inputBuffer = inputBuffer.encode("utf-8")

                #________FRAGMENTED MESSAGE________
                if len(inputBuffer) > fragmentSize:
                    packets = fragmentMessage(inputBuffer)

                    ARQ(packets, recieverAddr)


                #_____NOT-FRAGMENTED MESSAGE________
                else:
                    packet = protocol.Protocol()
                    packet.setType("MSG")
                    packet.setFrag("NO")
                    packet.setData(inputBuffer)

                    ARQ([packet], recieverAddr)



        #_______________REMAIN CONNECTION_____________
        # ak sa 5 sekund neodosle sprava, tak sa posle REMAIN CONNECTION packet, ak na neho pride odpoved, tak cely tento cyklus zacne od znova, ak ale nepride odpoved, tak sa este 2x skusi poslat REMAIN CONNECTION a ak ani na jeden nedostane odpoved, mozeme povazovat komunikaciu za uzavretu a preto sa TRANSMITTER ukonci
        else:

            #vytvorenie packetu pre udrzanie spojenia
            remainConneciton = protocol.Protocol()
            remainConneciton.setType("REMAIN CONNECTION")


            #v tomto pripade sa posle REMAINCONNECTION sprava a caka sa na odpoved - idealna situacia: reciever dostane tuto spravu a naspat posle packet typu REMAIN CONNECTION
            #ak odpoved nepride, zopakuje sa to este 2x kazdych 5 sekund, ak pride odpoved, tak ^
            #ak ani potom nepride ziadna odpoved, tak to znamena, ze sa neda nadviazat spojenie - treba ukoncit transmitter

            sock.settimeout(5)

            for _ in range(3):
                sock.sendto(remainConneciton.getFullPacket(), recieverAddr)
                
                try:
                    remainConnecitonAckPacket, recieverAddr = sock.recvfrom(1024)
                    #print("Checking for connection")
                    break
                except (TimeoutError, ConnectionResetError):
                    continue
            
            else:
                print("Could not reach, type CLOSE TRANSMITTER to close the transmitter")
                return 


            #ak dostal odpoved, kontrola ci to je odpoved na REMAIN CONNECTION, ktory bol poslany
            remainConnecitonAck = protocol.Protocol()
            remainConnecitonAck.buildFromBytes(remainConnecitonAckPacket)


            if remainConnecitonAck.getType() == "REMAIN CONNECTION":
                #print("Connection was maintained") 
                continue
            else:
                print("Error - not REMAIN CONNECTION recieved")
                return


def simulateError() -> None:
    
    inputBuffer = "9"*65540
    
    packets = fragmentMessage(inputBuffer.encode("utf-8"))

    ARQ(packets, recieverAddr, True)




if __name__ == "__main__":
    commType = input("R - RECIEVER, T - TRANSMITTER, K - KILL ")

    """ip = bytes(input("IP: "), "utf-8")
    port = int(input("PORT: "))
    fragmentSize = int(input("Select fragment size: "))"""

    fragmentSize = 1


    addr = ("localhost", 12345)

    sock = socket(AF_INET, SOCK_DGRAM)

    cli = Thread(target=CLI)
    cli.start()

    node = ''
    

    while switchFlag:
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

        if switchFlag:
            commType = 'R' if commType == 'T' else 'T'
            

    cli.join()