import numpy as np
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QMetaObject
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QDialog, QMessageBox

from GlobalMap import GlobalMap
from SpinBoxDelegate import SpinBoxDelegate
from Ui.Ui_RequestDialog import Ui_RequestDialog


class RequestDialog(QDialog, Ui_RequestDialog):
    def __init__(self, parent=None):
        super(RequestDialog, self).__init__(parent)
        self.setupUi(self)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.num_process = GlobalMap.get('num_process')
        self.num_resource = GlobalMap.get('num_resource')
        self.available = GlobalMap.get('available')
        self.allocation = GlobalMap.get('allocation')
        self.max_need = GlobalMap.get('max_need')

    def showEvent(self, a0: QtGui.QShowEvent):
        # 尚未分配资源，退出
        if not GlobalMap.get('init'):
            QMessageBox.warning(self, '错误', '请先初始化！')
            QMetaObject.invokeMethod(self, 'close', QtCore.Qt.QueuedConnection)
            return

        self.spinBox.setMaximum(self.num_process - 1)

        model = QStandardItemModel()
        model.setColumnCount(2)
        model.setHeaderData(0, QtCore.Qt.Horizontal, "资源种类")
        model.setHeaderData(1, QtCore.Qt.Horizontal, "资源数量")
        for i in range(self.num_resource):
            idx = QStandardItem(str(i))
            idx.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            model.setItem(i, 0, idx)
            # 设置默认请求向量为0
            model.setItem(i, 1, QStandardItem("0"))

        self.tableView.setItemDelegateForColumn(1, SpinBoxDelegate())
        self.tableView.setModel(model)

    def accept(self):
        # 读取输入的请求向量
        request = np.zeros((self.num_resource, 1), dtype=np.int)
        for i in range(self.num_resource):
            request[i] = int(self.tableView.model().item(i, 1).text())

        # 输入了全0请求向量
        if not request.any():
            QMessageBox.warning(self, '错误', '未设定分配资源数量')
            return

        # 读取请求资源的进程编号
        process = int(self.spinBox.text())

        # 运行银行家算法
        if self.banker_algorithm(request, process):
            QDialog.accept(self)

    def banker_algorithm(self, request, process):
        # 分配矩阵不存在，表示资源尚未分配，创建全零分配矩阵
        if self.allocation is None:
            self.allocation = np.zeros((self.num_process, self.num_resource), dtype=np.int)

        # 生成需求矩阵
        need = self.max_need - self.allocation

        if (request.T > need[process]).any():
            QMessageBox.warning(self, '错误', '所需要的资源数已超过所宣布的最大值')
            return False

        if (request > self.available).any():
            QMessageBox.warning(self, '错误', '尚无足够资源，请等待')
            return False

        # 尝试分配资源，更新可利用资源向量、分配矩阵和需求矩阵
        self.available -= request
        self.allocation[process] = self.allocation[process] + request.T
        need[process] = need[process] - request.T

        # 运行安全检查算法，得到安全状态和一个安全序列
        safe, safe_list = self.safety_algorithm()
        # 安全检查通过，保存新的可利用资源向量和分配矩阵，完成分配
        if safe:
            GlobalMap.set('available', self.available)
            GlobalMap.set('allocation', self.allocation)
            QMessageBox.warning(self, '提示', '分配成功，安全序列为%s' % safe_list)
            return True

        # 安全检查失败，回滚
        self.available += request
        self.allocation[process] = self.allocation[process] - request.T
        need[process] = need[process] + request.T
        QMessageBox.warning(self, '错误', '分配失败，否则系统将处于不安全状态')

    def safety_algorithm(self):
        # 工作向量，表示系统可提供给进程继续运行所需的各类资源数目，开始时与available相等
        work = self.available.copy()

        # 表示系统是否有足够的资源分配给进程，使之运行完成，开始时全为false
        finish = np.zeros(self.num_process, dtype=np.bool)

        # 生成需求矩阵
        need = self.max_need - self.allocation

        # 创建空安全序列
        safe_list = []

        # 当有进程未完成时，进行安全检查
        while False in finish:
            # 找到未完成且需求小于工作向量的所有进程
            todo = [i for i in range(self.num_process) if not finish[i] and (need[i] <= work.T).all()]
            # 若不存在这样的进程，退出循环
            if not todo:
                break
            # 当进程获得资源后，可顺利执行，直至完成，并释放出分配给它的资源，更新工作向量
            work += np.sum(self.allocation[todo], axis=0, keepdims=True).T
            # 标记进程已完成
            finish[todo] = True
            # 将进程加入安全序列
            safe_list.extend(todo)

        # 有任务没完成，处于不安全状态
        if False in finish:
            return False, None

        # 全部任务完成，处于安全状态
        return True, safe_list
