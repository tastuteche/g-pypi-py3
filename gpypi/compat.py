from yolk.pypi import CheeseShop
pypi = CheeseShop()


def get_python_compat(package_name, version):
    result = pypi.release_data("ipgetter", "0.6")
    # print(result["classifiers"])
    py_versions = []
    st = "Programming Language :: Python :: "
    for s in result["classifiers"]:
        if s.startswith(st):
            entry = s.replace(st, "")
            if entry == '2':
                py_versions.extend(['2_7'])
            elif entry == '3':
                py_versions.extend(['3_3', '3_4', '3_5'])
            elif entry == '2.6':
                py_versions.extend(['2_7'])
            elif entry == '2.7':
                py_versions.extend(['2_7'])
            elif entry == '3.2':
                py_versions.extend(['3_3'])
            elif entry == '3.3':
                py_versions.extend(['3_3'])
            elif entry == '3.4':
                py_versions.extend(['3_4'])
            elif entry == '3.5':
                py_versions.extend(['3_5'])

    if not py_versions:
        py_versions = ['2_7', '3_3', '3_4', '3_5']
    # print(py_versions)

    if len(py_versions) == 1:
        python_compat = '( python' + py_versions[0] + ' )'
    else:
        python_compat = '( python{' + py_versions[0]
        for ver in py_versions[1:]:
            python_compat += ',' + ver
        python_compat += '} )'

    # print(python_compat)
    return python_compat


if __name__ == '__main__':
    print(get_python_compat("ipgetter", "0.6"))
