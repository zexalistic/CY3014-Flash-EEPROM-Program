import clr
import os
import math
import logging
import time

clr.AddReference(os.path.join(os.path.dirname(__file__), 'CyUSB.dll'))
from System import UInt32, Single, Int32, Array
from System import Byte, Boolean

from CyUSB import USBDeviceList
from CyUSB import CyUSBDevice
from CyUSB import CyConst


class cyUSBWrapClass:
    def __init__(self, USBCardID, SMIPort):
        self.CardID = USBCardID
        self.SMIPort = SMIPort
        self.usbDevices = USBDeviceList(Byte(0x1))
        # print(self.usbDevices.Count)
        if self.usbDevices.Count == 0:
            print("cyUSB Device Count = 0")
        else:
            self.myDevice = self.usbDevices[0]
            self.BulkOut2 = self.myDevice.EndPointOf(2)
            self.BulkIn6 = self.myDevice.EndPointOf(0x86)
            self.CtrlEndPt = self.myDevice.ControlEndPt

    def ep2Write(self, data):
        data_listU = [Byte(data[i]) for i in range(len(data))]
        res = self.BulkOut2.XferData(data_listU, Int32(len(data_listU)))
        return res

    def ep6Read(self, data):
        data_listU = [Byte(data[i]) for i in range(len(data))]
        ret = self.BulkIn6.XferData(data_listU, Int32(len(data_listU)))
        result_list = list(ret[1])
        resultData_list = [str(hex(result_list[i])) for i in range(ret[2])]
        return resultData_list

    def read_fw_id(self) -> str:
        """
        Read firmware ID from RAM

        :return: string length of 8 indicating firmware ID
        """
        LENGTH_OF_FW_ID = 8
        self.CtrlEndPt.Target = CyConst.TGT_DEVICE
        self.CtrlEndPt.ReqType = CyConst.REQ_VENDOR
        self.CtrlEndPt.Direction = CyConst.DIR_FROM_DEVICE
        self.CtrlEndPt.ReqCode = 0xB0
        self.CtrlEndPt.Value = 0x0
        self.CtrlEndPt.Index = 0

        data_listU = [Byte(0) for i in range(LENGTH_OF_FW_ID)]
        ret = self.CtrlEndPt.XferData(data_listU, Int32(LENGTH_OF_FW_ID))
        ret = [chr(i) for i in list(ret[1])]
        ret = ''.join(ret)
        return ret

    def read_fw_version(self) -> str:
        """
        Read firmware version

        :return: string length of 8 indicating firmware version
        """
        self.CtrlEndPt.Target = CyConst.TGT_DEVICE
        self.CtrlEndPt.ReqType = CyConst.REQ_VENDOR
        self.CtrlEndPt.Direction = CyConst.DIR_FROM_DEVICE
        self.CtrlEndPt.ReqCode = 0xC8
        self.CtrlEndPt.Value = 0x0
        self.CtrlEndPt.Index = 0

        data_listU = [Byte(0) for i in range(8)]
        ret = self.CtrlEndPt.XferData(data_listU, Int32(8))
        ret = list(ret[1])
        ret = str((ret[1]<<8) + ret[0]) + '.' + str((ret[3]<<8) + ret[2]) + '.' + str((ret[5]<<8) + ret[4]) + '.' + str((ret[7]<<8) + ret[6])
        return ret

    def write_to_i2c_eeprom(self, eeprom_slave_addr: int, reg_addr: int, data_to_write: list) -> int:
        """
        Write to Cyress EEPROM through I2C.
        The default slave address for Cypress EEPROM lower 64Kb is set as 0 and upper 64KB is set as 4, and image begins from 0.
        EEPROM buffer size is 128B.

        :param eeprom_slave_addr:I2C EEPROM Slave Address (Can be in the 0 to 7 range, must be set according to the EEPROM address switch SW40)
        :param reg_addr: EEPROM byte address (can vary from 0x0000 to 0xFFFF. The max address is capped by the EEPROM max size)
        :param data_to_write: list of integer data to write. Length of data to be written (Should be a multiple of 64 and less than or equal to 4096)
        :return: Integer indicting success or not
        """
        length = len(data_to_write)
        if length < 0 or length > 4096:
            logging.error(f'Length of data to be written should be a multiple of 64 and less than or equal to 4096.')
            return -1
        if length % 64 != 0:
            data_to_write = data_to_write + [0 for i in range(64 - (length % 64))]  # filled with zeros
            length = len(data_to_write)

        self.CtrlEndPt.Target = CyConst.TGT_DEVICE
        self.CtrlEndPt.ReqType = CyConst.REQ_VENDOR
        self.CtrlEndPt.Direction = CyConst.DIR_TO_DEVICE
        self.CtrlEndPt.ReqCode = 0xBA
        self.CtrlEndPt.Value = eeprom_slave_addr
        self.CtrlEndPt.Index = reg_addr & 0xffff

        data_listU = [Byte(i) for i in data_to_write]
        ret = self.CtrlEndPt.XferData(data_listU, Int32(length))
        return ret[0]

    def read_from_i2c_eeprom(self, eeprom_slave_addr: int, reg_addr: int, length: int) -> list:
        """
        Read from I2C eeprom.
        The default slave address for Cypress EEPROM lower 64Kb is set as 0 and upper 64KB is set as 4, and image begins from 0.
        EEPROM buffer size is 128B.

        :param eeprom_slave_addr:I2C EEPROM Slave Address (Can be in the 0 to 7 range, must be set according to the EEPROM address switch SW40)
        :param reg_addr: EEPROM byte address (can vary from 0x0000 to 0xFFFF. The max address is capped by the EEPROM max size)
        :param length: Length of data to be written (Should be a multiple of 64 and less than or equal to 4096)
        :return: list of integer
        """
        if length < 0 or length > 4096:
            logging.error('length should be less than 4096.')
            return list()
        if length % 64 != 0:
            logging.warning('length should be a multiple of 64')
            length = 64 * (length / 64 + 1)

        self.CtrlEndPt.Target = CyConst.TGT_DEVICE
        self.CtrlEndPt.ReqType = CyConst.REQ_VENDOR
        self.CtrlEndPt.Direction = CyConst.DIR_FROM_DEVICE
        self.CtrlEndPt.ReqCode = 0xBB
        self.CtrlEndPt.Value = eeprom_slave_addr
        self.CtrlEndPt.Index = reg_addr & 0xffff

        data_listU = [Byte(0) for i in range(length)]
        ret = self.CtrlEndPt.XferData(data_listU, Int32(length))
        ret = list(ret[1])
        return ret

    def write_to_spi_flash(self, flash_page_number: int, data_to_write: list) -> int:
        """
        Write flash through SPI

        :param flash_page_number: page number of SPI flash page address (Each page is 256 bytes and the byte address is computed by multiplying page number by 256)
        :param data_to_write: list of integer indicating data to write. Length of data to be written (Should be a multiple of 256 and less than or equal to 4096)
        :return: integer indicating if success
        """
        length = len(data_to_write)
        if length < 0 or length > 4096:
            logging.error(f'Length of data to be written should be a multiple of 256 and less than or equal to 4096.')
            return -1
        if length % 256 != 0:
            data_to_write = data_to_write + [0 for i in range(256 - (length % 256))]  # filled with zeros
            length = len(data_to_write)
        self.CtrlEndPt.Target = CyConst.TGT_DEVICE
        self.CtrlEndPt.ReqType = CyConst.REQ_VENDOR
        self.CtrlEndPt.Direction = CyConst.DIR_TO_DEVICE
        self.CtrlEndPt.ReqCode = 0xC2
        self.CtrlEndPt.Value = 0x0
        self.CtrlEndPt.Index = flash_page_number

        data_listU = [Byte(i) for i in data_to_write]
        ret = self.CtrlEndPt.XferData(data_listU, Int32(length))
        return ret[0]

    def read_from_spi_flash(self, flash_page_number: int, length: int) -> list:
        """
        read flash through spi

        :param flash_page_number: page number of SPI flash page address (Each page is assumed to be of 256 bytes and the byte address is
                      computed by multiplying wIndex by 256)
        :param length: Length of data to be read (Should be a multiple of 256 and less than or equal to 4096)
        :return: list of integer
        """
        if length < 0 or length > 4096:
            logging.error('length should be less than 4096.')
            return list()
        if length % 256 != 0:
            logging.warning('length should be a multiple of 256')
            length = 256 * (length / 256 + 1)

        self.CtrlEndPt.Target = CyConst.TGT_DEVICE
        self.CtrlEndPt.ReqType = CyConst.REQ_VENDOR
        self.CtrlEndPt.Direction = CyConst.DIR_FROM_DEVICE
        self.CtrlEndPt.ReqCode = 0xC3
        self.CtrlEndPt.Value = 0x0
        self.CtrlEndPt.Index = flash_page_number

        data_listU = [Byte(0) for i in range(length)]
        ret = self.CtrlEndPt.XferData(data_listU, Int32(length))
        ret = list(ret[1])
        return ret

    def erase_spi_flash_block(self, block_number: int) -> bool:
        """
        Erase flash sector through SPI in 64KB

        :param block_number: SPI flash block_number (Each block is assumed to be of 64 KB and the byte address is computed by multiplying block number by 65536
        :return: if success
        """
        self.CtrlEndPt.Target = CyConst.TGT_DEVICE
        self.CtrlEndPt.ReqType = CyConst.REQ_VENDOR
        self.CtrlEndPt.Direction = CyConst.DIR_FROM_DEVICE
        self.CtrlEndPt.ReqCode = 0xC4
        self.CtrlEndPt.Value = 0x1      # non zero value means erase is true
        self.CtrlEndPt.Index = block_number
        data_listU = [Byte(0) for i in range(1)]
        ret = self.CtrlEndPt.XferData(data_listU, Int32(1))
        ret = list(ret[1])
        return ret[0] == 70

    def check_spi_busy_status(self) -> int:
        """
        Data phase will indicate SPI flash busy status

        :return:0x00 means SPI flash has finished write/erase operation and is ready for next command.
                0x1 means that SPI flash is still busy processing previous write/erase command.
        """
        self.CtrlEndPt.Target = CyConst.TGT_DEVICE
        self.CtrlEndPt.ReqType = CyConst.REQ_VENDOR
        self.CtrlEndPt.Direction = CyConst.DIR_FROM_DEVICE
        self.CtrlEndPt.ReqCode = 0xC4
        self.CtrlEndPt.Value = 0x0
        self.CtrlEndPt.Index = 0

        data_listU = [Byte(0) for i in range(2)]
        ret = self.CtrlEndPt.XferData(data_listU, Int32(2))
        ret = list(ret[1])[0]
        return ret & 0x1

    def wait_for_spi_flash_ready(self, timeout: int):
        """
        Wait until spi flash is not busy or time out

        :param timeout: Integer indicating the timeout duration in second
        :return: None
        """
        cnt = 0
        while MyDevice.check_spi_busy_status() and cnt < timeout * 10:
            time.sleep(0.1)
            cnt += 1
        if cnt == timeout * 10:
            logging.error('Time out!!')

    def read_spi_flash_id(self) -> int:
        """
        Read the device ID of spi flash. The first byte is always 0xEF, the second byte is device ID.

        :return: 0xef if SPI flash operates in normal state
        """
        self.CtrlEndPt.Target = CyConst.TGT_DEVICE
        self.CtrlEndPt.ReqType = CyConst.REQ_VENDOR
        self.CtrlEndPt.Direction = CyConst.DIR_FROM_DEVICE
        self.CtrlEndPt.ReqCode = 0xC5
        self.CtrlEndPt.Value = 0x0
        self.CtrlEndPt.Index = 1

        data_listU = [Byte(0) for i in range(2)]
        ret = self.CtrlEndPt.XferData(data_listU, Int32(2))
        ret = list(ret[1])[0]
        return ret

    def reset_fx3(self):
        """
        Request used to cause FX3 to reset itself. This command can be used at the end of a flashing
        session to cause FX3 to reset and load the newly flashed firmware from SPI Flash or I2C
        EEPROM.

        :return:
        """
        self.CtrlEndPt.Target = CyConst.TGT_DEVICE
        self.CtrlEndPt.ReqType = CyConst.REQ_VENDOR
        self.CtrlEndPt.Direction = CyConst.DIR_TO_DEVICE
        self.CtrlEndPt.ReqCode = 0xE0
        self.CtrlEndPt.Value = 0x0
        self.CtrlEndPt.Index = 0

        data_listU = [Byte(0) for i in range(0)]
        ret = self.CtrlEndPt.XferData(data_listU, Int32(0))
        time.sleep(3)
        return ret[0]

    def upgrade_eeprom_via_i2c(self, bin_file_name: str):
        """
        Upgrade EEPROM image over I2C

        :param bin_file_name: name of bin file
        :return: None
        """
        with open(bin_file_name, 'rb') as fp:
            img = fp.read()
            img = list(img)
            idx = 0
            while idx <= len(img):       # The lower 64KB
                data = img[idx:idx + 128]
                if idx < 0x10000:
                    self.write_to_i2c_eeprom(0, idx, data)
                    time.sleep(0.1)  # maximum 5ms write delay
                    idx += 128
                else:
                    self.write_to_i2c_eeprom(4, idx, data)
                    time.sleep(0.1)  # maximum 5ms write delay
                    idx += 128

    def dump_eeprom_via_i2c(self, bin_file_name: str):
        """
        Dump eeprom content to bin file over I2C .

        :param bin_file_name: name of bin file
        :return: None
        """
        with open(bin_file_name, 'wb') as fp:
            idx = 0
            while idx < 0x10000:    # The lower 64KB
                data = self.read_from_i2c_eeprom(0, idx, 128)
                fp.write(bytes(data))
                idx += 128
            while idx < 0x20000:    # The upper 64KB
                data = self.read_from_i2c_eeprom(4, idx, 128)
                fp.write(bytes(data))
                idx += 128

    def upgrade_fpga_firmware_over_spi(self, bin_file_name: str):
        """
        Upgrade fpga firmware to flash over SPI bus

        :param bin_file_name: name of bin file
        :return: None
        """
        img = list()
        with open(bin_file_name, 'rb') as fp:
            img = list(fp.read())

        # Erase flash in 64KB blocks
        logging.info('Erasing flash..')
        number_of_blocks = math.ceil(len(img) / 0x10000)
        for blk in range(number_of_blocks):
            if not self.erase_spi_flash_block(blk):
                logging.error(f'Erase flash block {blk} fail.')
            self.wait_for_spi_flash_ready(timeout=10)
            prcnt = round(100 * blk/number_of_blocks, 2)
            logging.info(f'Percentage: {prcnt}%')
        logging.info('Erasing flash done.')

        logging.info('Writing flash..')
        idx = 0
        while idx <= len(img):
            data = img[idx:idx + 256]
            if not self.write_to_spi_flash(idx//256, data):
                logging.error(f'SPI write flash page {idx//256} fail.')
            self.wait_for_spi_flash_ready(timeout=10)
            idx += 256
            if ((idx/256) % 10) == 0:
                prcnt = round(100 * idx/len(img), 2)
                logging.info(f'Percentage: {prcnt}%')
        logging.info('Writing flash done.')

    def dump_flash_over_spi(self, bin_file_name: str, length: int):
        """
        Dump flash content to bin file over SPI .

        :param bin_file_name: name of bin file
        :param length: size of data to be dumped in KB. Should be a multiple of 256.
        :return: None
        """
        number_of_pages = length * 4
        idx = 0
        logging.info('Dumping flash..')
        with open(bin_file_name, 'wb') as fp:
            while idx < number_of_pages:
                data = self.read_from_spi_flash(idx, 256)
                self.wait_for_spi_flash_ready(timeout=10)
                fp.write(bytes(data))
                idx += 1
                if (idx % 100) == 0:
                    prcnt = round(100 * idx/ number_of_pages, 2)
                    logging.info(f'Percentage: {prcnt}%')
        logging.info('Dumping flash done.')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    mdioFirstPort = 0
    MyDevice = cyUSBWrapClass(bytes("0x47c2", 'utf-8'), 0)

    ret = MyDevice.switch_uart_to_spi_mode()
    print(ret)

    # MyDevice.upgrade_fpga_firmware_over_spi('cstb.bit')
    # time.sleep(1)
    # MyDevice.dump_flash_over_spi('out2.bin', 5840)


    # MyDevice.upgrade_eeprom_via_i2c('USBFlashProg.img')
    # MyDevice.reset_fx3()
    # MyDevice.dump_eeprom_via_i2c('out.bin')

    # ret = MyDevice.read_fw_id()
    # print(ret)
    # ret = MyDevice.read_fw_version()
    # print(ret)

    # ret = MyDevice.read_spi_flash_id()
    # print(hex(ret))

    # ret = MyDevice.read_from_spi_flash(2, 256)
    # print(ret)
    # ret = MyDevice.erase_spi_flash_block(0)
    # print(ret)
    # MyDevice.wait_for_spi_flash_ready(timeout=10)
    #
    # ret = MyDevice.read_from_spi_flash(64, 256)
    # print(ret)
    # ret = MyDevice.write_to_spi_flash(64, [(128-i) for i in range(128)])      # Write have bug
    # print(ret)
    # MyDevice.wait_for_spi_flash_ready(timeout=10)
    #
    # ret = MyDevice.read_from_spi_flash(64, 256)
    # print(ret)


