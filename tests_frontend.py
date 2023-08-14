import json, time, filecmp, pathlib, sys
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from microgridup import MGU_FOLDER


def test_browser_gui():
    options = Options()
    driver = webdriver.Chrome(options=options)

    driver.get('http://localhost:5000/')

    with open('testfiles/test_params.json') as file:
        test_params = json.load(file)
    crit_loads = test_params['crit_loads']
    MG_MINES = test_params['MG_MINES']
    algo_params = test_params['algo_params']
    pairings = algo_params['pairings']

    for _dir in MG_MINES:
        driver.find_element(By.XPATH, '//a[@href][text()="+"]').click()

        print(f'---------------------------------------------------------\nBeginning end-to-end test of {_dir}.\n---------------------------------------------------------')

        MODEL_DIR = driver.find_element(By.NAME, 'MODEL_DIR')
        MODEL_DIR.clear()
        MODEL_DIR.send_keys(f'{_dir}')

        driver.find_element(By.NAME, 'LOAD_CSV').send_keys(f'{MGU_FOLDER}/testfiles/lehigh_load.csv')

        if 'lehigh' in _dir:
            driver.find_element(By.ID, 'upload').click()

            driver.find_element(By.NAME, 'BASE_DSS_NAME').send_keys(f'{MGU_FOLDER}/testfiles/lehigh_base_3mg.dss')

            driver.find_element(By.ID, 'upload-file-btn').click()
        
        elif 'wizard' in _dir:
            driver.find_element(By.ID, 'wizard').click()

            # JavaScript shortcut.
            driver.execute_script('fillWizardLehigh()')

            # TO DO: Fill out circuit wizard with Selenium rather than using a JavaScript shortcut.
            # driver.find_element(By.XPATH, '//ul[@id="elements"]//li[@class="substation"]').click()
            # driver.find_element(By.XPATH, '//ul[@id="elements"]//input[@class="substation"]').send_keys(' sub')

            driver.find_element(By.ID, 'toDss').click()


        time.sleep(2)

        crit_loads = ['634a_data_center', '634b_radar', '634c_atc_tower', '675a_hospital', '675b_residential1', '675c_residential1', '645_hangar', '646_office']
        for load in crit_loads:
            checkbox = driver.find_element(By.XPATH, f'//label[text()="{load}"]')
            checkbox.click()
        
        algo = MG_MINES[_dir][1]
        select = Select(driver.find_element(By.ID, 'partitionMethod'))
        select.select_by_value(f'{MG_MINES[_dir][1]}')

        if algo in ('loadGrouping','manual'):
            driver.find_element(By.ID, 'mgQuantity').send_keys('3')
            driver.find_element(By.ID, 'makeDropdownsButton').click()
            # Fill out dropdowns.
            pairings.pop('None','')
            for key in pairings:
                for load in pairings[key]:
                    select = Select(driver.find_element(By.XPATH, f'//div[@id="dropDowns"]//label[text()=" {load}"]/select'))
                    select.select_by_value(key)
            if algo == 'manual':
                # Fill out switches and gen buses.
                switch = algo_params['switch']
                gen_bus = algo_params['gen_bus']
                for key in switch:
                    driver.find_element(By.ID, f'{key.lower()}Switch').send_keys(switch[key])
                    driver.find_element(By.ID, f'{key.lower()}Genbus').send_keys(gen_bus[key])
        elif algo in ('bottomUp','criticalLoads'):
            driver.find_element(By.ID, 'minQuantMgs').send_keys('3')
            driver.find_element(By.ID, 'previewPartitionsButton').click()
        else:
            driver.find_element(By.ID, 'previewPartitionsButton').click()

        time.sleep(2)

        technologies = ['fossil'] # 'solar' and 'battery' are checked by default when loading in data/static/lehigh_3mg_inputs.json.
        for tech in technologies:
            driver.find_element(By.NAME, f'{tech}').click()

        time.sleep(1)
        
        driver.find_element(By.ID, 'submitEverything').click()

        time.sleep(20)
    return


def test_browser_gui_output():
    '''
    - Test that the automated selenium tests are creating the output that is expected by the back-end tests in microgridup.py. If there is a file
      mismatch between the output generated by selenium and a file in testfiles/, then either selenium isn't working properly or the files in
      testfiles/ need to be updated
    '''
    filecmp.clear_cache()
    load_shape_path = (pathlib.Path(__file__).resolve(True).parent / 'testfiles' / 'lehigh_load.csv')
    lehigh_dss_path = (pathlib.Path(__file__).resolve(True).parent / 'testfiles' / 'lehigh_base_3mg.dss')
    wizard_dss_path = (pathlib.Path(__file__).resolve(True).parent / 'testfiles' / 'wizard_base_3mg.dss')
    mismatched_files = []
    for child in (pathlib.Path(__file__).resolve(True).parent / 'uploads').iterdir():
        if str(child.stem).lower().find('load_csv') > -1:
            if not filecmp.cmp(load_shape_path, child):
                mismatched_files.append((str(child.stem), 'lehigh_load.csv'))
        elif str(child.stem).lower().find('lehigh') > -1:
            if not filecmp.cmp(lehigh_dss_path, child):
                mismatched_files.append((str(child.stem), 'lehigh_base_3mgs.dss'))
        elif str(child.stem).lower().find('wizard') > -1:
            # - wizard_base_3mg.dss has a generic circuit name while tests_frontend.py outputs DSS files with specific circuit names. I have to delete
            #   the circuit name to compare the rest of the files
            with open(child) as f:
                child_contents = f.readlines()
            child_contents.pop(2)
            with open(wizard_dss_path) as f:
                dss_contents = f.readlines()
            dss_contents.pop(2)
            if not child_contents == dss_contents:
                mismatched_files.append((str(child.stem), 'wizard_base_3mg.dss'))
        else:
            raise Exception(f'Unrecognized file in uploads/ directory: {str(child.stem)}')
    if len(mismatched_files) > 0:
        for mismatch in mismatched_files:
            print(f'The file "{mismatch[0]}" was expected to match "{mismatch[1]}", but the file contents were different.')
        sys.exit(1) # trigger failure
    print('All files output in uploads/ by tests_frontend.py matched the expected content and format of the back-end test input files.')


if __name__ == '__main__':
    test_browser_gui()
    test_browser_gui_output()