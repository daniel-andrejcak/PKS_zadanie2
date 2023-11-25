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

switchFlag = True

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

def checksum(packet: protocol.Protocol, divisor=0x11021) -> bool:
    word = packet.getData()
    word = int.from_bytes(word.encode("utf-8"), byteorder='big')
    word <<= 16

    while word.bit_length() > 16:

        if word.bit_length() > divisor.bit_length():
            divisor <<= (word.bit_length() - divisor.bit_length())
        else:
            divisor >>= (divisor.bit_length() - word.bit_length())

        word ^= divisor

    word = protocol.pack('>H', word)

    return packet.getChecksum() == word




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
            
            send(closeAck, transmitterAddr)



        #______________SWITCH______________
        elif protocolFormatMsg.getType() == "SWITCH":

            print(f"TRANSMITTER on {transmitterAddr} initialized switch.")

            switchAck = protocol.Protocol()
            switchAck.setType("SWITCH")
            
            send(switchAck, transmitterAddr)

            #TODO zmena adries a portov + vynulovanie identifier 
            identifier = 0
            recieverAddr, transmitterAddr = transmitterAddr, recieverAddr

            sock.close()

            switchFlag = True
            return



        #________REMAIN CONNECTION_________
        #ak prijeme spravu REMAIN CONNECTION, tak naspat posle taku istu spravu - to sluzi ako ACK pre TRANSMITTER
        elif protocolFormatMsg.getType() == "REMAIN CONNECTION":

            print("REMAIN CONNECTION message recieved, sending ACK...")

            remainConnctionAck = protocol.Protocol()
            remainConnctionAck.setType("REMAIN CONNECTION")

            send(remainConnctionAck, transmitterAddr)



        #MSG
        elif protocolFormatMsg.getType() == "MSG":

            #kontrola checksum, ak nesedi, tak posle nAck a transmitter posle znova
            if not checksum(protocolFormatMsg):
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


        #ak dostane nejaky neznamy type - poskodena sprava
        else:
            print("Error - wrong type of packet recieved")
            return



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
        for _ in range(10):
            try:
                inputBuffer = inputBufferQueue.pop()
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
                send(close, recieverAddr)

                #prijatie CLOSE spravy - potvrdenie CLOSE od RECIEVERa
                sock.settimeout(5)

                for _ in range(3):
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
                    print("Error - wrong ACK recieved")
                    return



            #vymena TRANSMITTER a RECIEVER
            #TRANSMITTER posle spravu SWITCH, RECIEVER dostane tuto spravu, posle odpoved, vymenia sa - idealna situacia
            #ak nedostane odpoved, posle este 2x kazdych 5sek, ak dostane odpoved ^
            #ak nedostane odpoved, tak napise spravu ze nic z toho a klasicky pokracuje dalej
            elif inputBuffer == "SWITCH":

                switch = protocol.Protocol()
                switch.setType("SWITCH")

                send(switch, recieverAddr)

                #prijatie SWITCH spravy - potvrdenie SWITCH od RECIEVERa
                sock.settimeout(5)
                for _ in range(3):
                    try:
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
                    print("Error - wrong ACK recieved")
                    return



            #__________SENDING FILE_____________
            elif len(inputBuffer) >= 4 and inputBuffer[:4 ] == "FILE":
                inputBuffer = inputBuffer[5:]

                packets = fragmentFile(inputBuffer)

                for packet in packets:
                    send(packet, recieverAddr)



            #__________SENDING MESSAGE__________
            else:
                #________FRAGMENTED MESSAGE________
                if len(inputBuffer) > fragmentSize:
                    packets = fragmentMessage(inputBuffer)

                    for packet in packets:
                        send(packet, recieverAddr)


                #_____NOT-FRAGMENTED MESSAGE________
                else:
                    packet = protocol.Protocol()
                    packet.setType("MSG")
                    packet.setFrag("NO")
                    packet.setData(inputBuffer)

                    send(packet, recieverAddr)



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
                send(remainConneciton, recieverAddr)
                
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