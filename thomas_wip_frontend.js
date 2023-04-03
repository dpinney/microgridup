var circuitIsSpecified = false;
var filename = '';

// Enable technology checkboxes.
$('[name="battery"]').change(function() {
    $('#batteryDiv').toggle(500);
});
$('[name="wind"]').change(function() {
    $('#windDiv').toggle(500);
});
$('[name="solar"]').change(function() {
    $('#solarDiv').toggle(500);
});
$('[name="fossil"]').change(function() {
    $('#fossilDiv').toggle(500);
});

// Enable circuit definition method choice.
$(document).ready(function() {
    $("div.desc").hide();
    $("input[name$='circuit']").click(function() {
        var test = $(this).val();

        $("div.desc").hide();
        $("#circuit" + test).show();
    });
});

// Editable text for circuit widget.
$('body').on('click', '[data-editable]', function(){
    var $og = $(this);
    var $input = $('<input/>').val( $og.text() ).addClass( $og.attr('class') ).select();
    $og.replaceWith( $input );
    // Ensure element type remains uneditable in circuit widget.
    var base = $og.attr('class').charAt(0).toUpperCase() + $og.attr('class').slice(1) + ': ';
    var regex = new RegExp("^" + base, "i");
    $('#elements input').on("input", function(ev) {
        var query = $(this).val();
        if (!regex.test(query)) {
            ev.preventDefault();
            $(this).val(base);
        }
    });
    // Save on click or enter key press.
    var save = function(){
        var $p = $('<li data-editable />').html('<i class="fa fa-minus-square"></i> ' + $input.val() ).addClass( $og.attr("class") );
        $input.replaceWith( $p );
    };
    $input.on('blur keypress', function(e) {
        if (e.type == 'blur' || e.keyCode == 13) {
            save();
        }
    }).focus();
});

// Delete elements with click of icon in circuit widget. Delete all downstream elements as well.
$('body').on('click', '#elements li i', function(){
    var type = $(this).parent($('li')).attr('class');
    var downstream = {
        'substation':['feeder','load','wind','solar','battery','diesel'],
        'feeder':['load','wind','solar','battery','diesel']
    }
    // Warn user that downstream nodes will be deleted if they proceed.
    if (type in downstream && $(this).parent($('li')).next('li').length > 0) {
        if (downstream[type].includes($(this).parent($('li')).next('li').attr('class'))) {
            if (confirm("All elements on the substation/feeder to be deleted will also be deleted. Continue?") == false) {
                return
            } 
            delete_these = downstream[type]
            while ($(this).parent($('li')).next('li').length > 0 && delete_these.includes($(this).parent($('li')).next('li').attr('class'))) {
                $(this).parent($('li')).next('li').remove();
            }
        }
    }
    $(this).parent($('li')).remove();
});

// Either add a new substation to the bottom or open up dialog.
$('#newSub, #newFeeder, #newLoad, #newSolar, #newWind, #newBattery, #newDiesel').on('click', function() {
    $('#dialog select').empty();
    $('#dialogText').removeClass();
    let type = $(this).attr('id');
    let map = {'newSub':['substation'],'newFeeder':['feeder','substation'],'newLoad':['load','feeder'],'newSolar':['solar','feeder'],'newWind':['wind','feeder'],'newBattery':['battery','feeder'],'newDiesel':['diesel','feeder']}
    let name = ' '+map[type][0].charAt(0).toUpperCase()+map[type][0].slice(1)+': (click to name)'
    if (type === 'newSub') {
        $("#elements").append('<li class="substation" data-editable><i class="fa fa-minus-square"></i>'+name+'</li>');
    } else {
        var all = $("#elements ." + map[type][1]).map(function() {
            let idx = this.innerHTML.indexOf(': ') + 2;
            return this.innerHTML.slice(idx);
        }).get();
        $("#dialogText").text("To which "+map[type][1]+" would you like to add a "+map[type][0]+"?").addClass(map[type][0]+' '+map[type][1]);
        for (let idx = 0; idx < all.length; idx++) {
            $('#dialog select').append(`<option value="${all[idx]}">${all[idx]}</option>`);
        }
        window.dialog.showModal();
    }
});
// Close dialog and add non-substation element.
$('#dialog button[type="button"]').on('click', function() {
    window.dialog.close()
    let parentName = $('#dialog select').val();
    let type = $('#dialogText').attr('class').split(' ')[0];
    let parentType = $('#dialogText').attr('class').split(' ')[1];
    let child = ' '+type.charAt(0).toUpperCase()+type.slice(1)+': (click to name)';
    let parent = ' '+parentType.charAt(0).toUpperCase()+parentType.slice(1)+': '+parentName;
    $('<li class="'+type+'" data-editable><i class="fa fa-minus-square"></i>'+child+'</li>').insertAfter('#elements li:contains('+parent+')')
});

// Create DSS from manually built circuit. Get loads.
$(function() {
    $('#toDss').click(function() {
        // Do not proceed if model has no name.
        if ($('input[name="MODEL_DIR"]').val() === '') {
            alert('Please specify a model name.')
            return 
        }
        // First, convert to list. Then, convert to JSON.
        var list = [];
        $('#elements li').each(function(idx, item){
            var fullName = item.textContent;
            var startIdx = fullName.indexOf(':') + 2;
            list.push({
                class: $(item).attr('class'),
                text: fullName.slice(startIdx)
            });
        });
        json = JSON.stringify(list, null, "  ");
        console.log(json)

        // Add MODEL_DIR to json.
        const form_data = new FormData();
        form_data.append('json',json);
        var model_dir = $('input[name="MODEL_DIR"]').val()
        form_data.append('MODEL_DIR',model_dir)

        // Add latitude and longitude to json.
        var latitude = $('input[name="latitude"]').val()
        form_data.append('latitude',latitude)
        var longitude = $('input[name="longitude"]').val()
        form_data.append('longitude',longitude)

        // Next, make AJAX POST to backend. 
        $.ajax({
            url:'/jsonToDss',
            type:'POST',
            contentType: false,
            data: form_data,
            processData : false,
            success: function(data) {
                circuitIsSpecified = true;
                const loads = data.loads;
                $('#critLoads').empty();
                $('#critLoads').append('<p>Please select all critical loads:</p>')
                $('#dropDowns').empty();
                $('#dropDowns').hide();
                jQuery('<form>', {
                    id: 'criticalLoadsSelect',
                    class: 'chunk'
                }).appendTo('#critLoads');
                for (let i=0; i<loads.length; i++) {
                    $('#criticalLoadsSelect').append('<label><input type="checkbox">'+loads[i]+'</label>')
                    $('#dropDowns').append('<label><select></select> '+loads[i]+'</label><br>')
                }
                if (loads.length === 0) {
                    $('#criticalLoadsSelect').append('<p>No loads to select from.</p>')
                }
                // Set filename.
                filename = data.filename;
                // Make directory uneditable. 
                $('input[name="MODEL_DIR"]').prop("readonly", true);	
                // Remove manual option from partitioning options because switches and gen_bus are predetermined.
                $("#partitionMethod option[value='manual']").remove();
            }
        });
    })
})

// Upload DSS circuit. Get loads.
$(function() {
    $('#upload-file-btn').click(function() {
        // Do not proceed if model has no name.
        if ($('input[name="MODEL_DIR"]').val() === '') {
            alert('Please specify a model name.')
            return 
        }
        var form_data = new FormData($('#upload-file')[0]);
        var model_dir = $('input[name="MODEL_DIR"]').val()
        form_data.append('MODEL_DIR',model_dir)
        $.ajax({
            type: 'POST',
            url: '/uploadDss',
            data: form_data,
            contentType: false,
            cache: false,
            processData: false,
            success: function(data) {
                circuitIsSpecified = true;
                const loads = data.loads;
                $('#critLoads').empty();
                $('#critLoads').append('<p>Please select all critical loads:</p>')
                $('#dropDowns').empty();
                $('#dropDowns').hide();
                jQuery('<form>', {
                    id: 'criticalLoadsSelect',
                    class: 'chunk'
                }).appendTo('#critLoads');
                for (let i=0; i<loads.length; i++) {
                    $('#criticalLoadsSelect').append('<label><input type="checkbox">'+loads[i]+'</label>')
                    $('#dropDowns').append('<label><select></select> '+loads[i]+'</label><br>')
                }
                if (loads.length === 0) {
                    $('#criticalLoadsSelect').append('<p>No loads to select from.</p>')
                }
                
                // Set filename.
                filename = data.filename;
                // Make directory uneditable. 
                $('input[name="MODEL_DIR"]').prop("readonly", true);
            }
        });
    });
});

// Manual partitioning dynamic dropdown creation. 
$('#makeDropdowns').on('click', function() {
    if (circuitIsSpecified === false) {
        alert('Please complete step 2.')
        return
    }
    if ($('#mgQuantity').val() === "") {
        alert('Please input a number.')
        return
    }
    // Manual grouping GUI includes inputs for gen_bus and switch.
    var numMgs = $('#mgQuantity').val();
    if ($('#partitionMethod').val() == 'manual') {
        // Clear existing #switchGenbus if it exists already. 
        $('#switchGenbus').remove();
        $('#dropDowns').prepend('<div id="switchGenbus"></div>')
        for (let i = 0; i < numMgs; i++) {
            var count = i + 1;
            $('#switchGenbus').append('<label for="mg' + count + 'Genbus">Mg' + count + ' Gen Bus: </label>');
            $('#switchGenbus').append('<input id="mg' + count + 'Genbus" type="text"></input>');
            $('#switchGenbus').append('<label for="mg' + count + 'Switch"> Mg' + count + ' Switch: </label>');
            $('#switchGenbus').append('<input id="mg' + count + 'Switch" type="text"></input>');
            $('#switchGenbus').append('<br>');
        }
    }
    $('#dropDowns label select').each(function() {
        $(this).empty();
        $(this).append('<option value="">None</option>')
        for (let i = 0; i < numMgs; i++) {
            var count = i + 1;
            $(this).append('<option value="">Mg' + count + '</option>');
        }
    });
    $('#dropDowns').show();
})
// Also call above function if user presses enter.
$('#mgQuantity').keypress(function(e){
    if (e.which === 13) {
        e.preventDefault();
        $('#makeDropdowns').click();
    }
});

// Hide/show manual partitioning div. 
$('#partitionMethod').change(function() {
    $('#minQuantMgs').val('');
    if ($(this).val() == 'manual' || $(this).val() == 'loadGrouping') {
        $('#partitionManually').show();
        $('#makeDropdowns').show();
        $('#previewPartitions').hide();
        $('#minQuantMgsForm').hide();
        $('#partitionsPreview').empty();
    }
    else { 
        $('#partitionManually').hide();
        $('#minQuantMgsForm').hide();
        $('#dropDowns').hide();
        $('#previewPartitions').show();
    }
    if ($(this).val() == 'loadGrouping') {
        $('#switchGenbus').remove();
    }
    if ($(this).val() == 'bottomUp' || $(this).val() == 'criticalLoads') {
        $('#minQuantMgsForm').show();
        $('#makeDropdowns').hide();
    }
})

  // Grab partitioning preview.
$(function() {
      $('#previewPartitions').click(function() {
          if (circuitIsSpecified === false) {
              alert('Please complete step 2.')
              return
          }
          // 1. Get critical loads, if any.
          critLoads = new Array();
          $('#criticalLoadsSelect label').each(function() {
              if ($(this).find('input')[0].checked) {
                  var element = $(this).text();
                  critLoads.push(element);
              }
          });
          console.log(critLoads);
          // 2. Get dss file name.
          console.log(filename);
          // 3. Get partitioning method.
          var method = $( "#partitionMethod option:selected" ).val();
          console.log(method);
          if (method === "") {
              alert('Please ensure you have chosen a partition method.');
              return
          }
        // 4. Get mgQuantity, if applicable. 
        var mgQuantity = $('#minQuantMgs').val() ? $('#minQuantMgs').val() : 0;
        console.log(mgQuantity);
          $.ajax({
              url: 'previewPartitions',
              type: 'POST',
              data: {
                  critLoads : JSON.stringify(critLoads),
                  fileName : JSON.stringify(filename),
                  method : JSON.stringify(method),
                mgQuantity : JSON.stringify(mgQuantity)
              },
              success: function(data, status) {
                  /* creating image */
                  var img = $('<img id="image_id">');
                  img.attr('src', 'data:image/gif;base64,' + data);
                  $('#partitionsPreview').empty();
                  img.appendTo('#partitionsPreview'); 
              }
          });
      });
});

// Show/hide optional inputs.
$(function () {
    $('.toggle').click(function() {
        if ( $(this).hasClass('show') ) {
            //replace the text
            $(this).text('Show fewer inputs');
            //replace the icon
            $(this).prev('i').removeClass('fa-plus-square').addClass('fa-minus-square');
            $(this).removeClass('show').addClass('hide');
        } else {
            //replace the text
            $(this).text('Optional inputs');
            //replace the icon
            $(this).prev('i').removeClass('fa-minus-square').addClass('fa-plus-square');
            $(this).removeClass('hide').addClass('show');                
        }
        $(this).next('div').slideToggle('500');
    });
});

// Submit everything. 
$(function() {
      $('#submitEverything').click(function() {
        // Do not proceed if no circuit is specified.
        if (filename === '') {
            alert('Please specify a circuit.')
            return 
        }
        // Do not proceed if no loads are specified.
        if ($('#LOAD_CSV')[0].files.length === 0) {
            alert('Please specify load data.')
            return 
        }
        // Do not proceed if no partition method is specified.
        if ($( "#partitionMethod option:selected" ).val() === '') {
            alert('Please specify a partitioning method.')
            return 
        }
        var form1 = new FormData(document.getElementById("modelInfoForm"));
          var form2 = new FormData(document.getElementById("techParamForm"));
        for (var pair of form2.entries()) {
                form1.append(pair[0], pair[1]);
            }
        // Append BASE_DSS as either uploaded file or creation.dss.
        var fileStringArray = [ filename ];
        var fileName = filename;
        var blobAttrs = { type: 'application/octet-stream' };
        var file = new File(fileStringArray, fileName, blobAttrs);
        form1.append('BASE_DSS', file, file.name);
        // Append CRITICAL_LOADS.
        critLoads = new Array();
          $('#criticalLoadsSelect label').each(function() {
              if ($(this).find('input')[0].checked) {
                  var element = $(this).text();
                  critLoads.push(element);
              }
          });
        form1.append('CRITICAL_LOADS',JSON.stringify(critLoads));
        // Append MG_DEF_METHOD. 
        var method = $( "#partitionMethod option:selected" ).val();
        form1.append('MG_DEF_METHOD',method);

        // Do not proceed if manual is selected and no partitions are created.
        if ((method === 'manual' && !$('#dropDowns').is(':visible')) || (method === 'loadGrouping' && !$('#dropDowns').is(':visible'))) {
            alert('Please enter a number of microgrids and press Go.')
            return
        }
        // If manual or loadGrouping is selected, append a 'MICROGRIDS' value.
        var MICROGRIDS = {}
        $('#dropDowns label').each( function() {
            // Skip the Gen Buses and Switches.
            if (this.hasAttribute('for')) {
                return true
            }
            console.log(this);
            var load = $(this).text().split(' ')[1]
            console.log('load');
            console.log(load);
            var mg = $(this).find(':selected').text()
            console.log('mg');
            console.log(mg);
            if (method === 'loadGrouping') {
                MICROGRIDS[mg] ??= [];
                MICROGRIDS[mg].push(load);
            }
            else if (method === 'manual') {
                MICROGRIDS.pairings ??= {};
                MICROGRIDS.pairings[mg] ??= [];
                MICROGRIDS['pairings'][mg].push(load); 
            }
        } )
        // If manual is selected, append switch and gen_bus values.
        var counter = 0;
        $('#switchGenbus input').each( function() {
            counter = counter + 0.5;
            var id = $(this).attr('id');
            var val = $(this).val();
            var mg = 'Mg' + Math.round(counter);
            if (id.includes('Genbus')) {
                MICROGRIDS.gen_bus ??= {};
                MICROGRIDS.gen_bus[mg] = val;
            } 
            else {
                MICROGRIDS.switch ??= {};
                MICROGRIDS.switch[mg] = val;
            }
        })
        console.log('MICROGRIDS');
        console.log(MICROGRIDS);
        form1.append('MICROGRIDS',JSON.stringify(MICROGRIDS));
        // Append mgQuantity. 
        var mgQuantity = $('#minQuantMgs').val() ? $('#minQuantMgs').val() : 0;
        form1.append('mgQuantity',JSON.stringify(mgQuantity));

        $.ajax({
            url: '/run',
            type: 'POST',
            data: form1,
            processData: false,
            contentType: false,
            success: function(data) {
                window.location.href = '/';
            }
        })
    })
});
var elements = `
<ul id="elements">
        <li data-editable="" class="substation"><i class="fa fa-minus-square" aria-hidden="true"></i> Substation: sub</li><li data-editable="" class="feeder"><i class="fa fa-minus-square" aria-hidden="true"></i>  Feeder: regNone</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 684_command_center</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 692_warehouse2</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 611_runway</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 652_residential</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 670a_residential2</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 670b_residential2</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 670c_residential2</li><li data-editable="" class="feeder"><i class="fa fa-minus-square" aria-hidden="true"></i> Feeder: reg0</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 634a_data_center</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 634b_radar</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 634c_atc_tower</li><li data-editable="" class="solar"><i class="fa fa-minus-square" aria-hidden="true"></i> Solar: solar_634_existing</li><li data-editable="" class="battery"><i class="fa fa-minus-square" aria-hidden="true"></i> Battery: battery_634_existing</li><li data-editable="" class="feeder"><i class="fa fa-minus-square" aria-hidden="true"></i> Feeder: reg1</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 675a_hospital</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 675b_residential1</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 675c_residential1</li><li data-editable="" class="diesel"><i class="fa fa-minus-square" aria-hidden="true"></i> Diesel: fossil_675_existing</li>
        <li data-editable="" class="feeder"><i class="fa fa-minus-square" aria-hidden="true"></i> Feeder: reg2</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 645_hangar</li><li data-editable="" class="load"><i class="fa fa-minus-square" aria-hidden="true"></i> Load: 646_office</li>
        
        
        
        
    </ul>
`
function fillWizardLehigh() {
    $('#elements').replaceWith(elements);
}

var dropDowns = `
<div id="dropDowns" class="chunk" style=""><div id="switchGenbus"><label for="mg1Genbus">Mg1 Gen Bus: </label><input id="mg1Genbus" type="text"><label for="mg1Switch"> Mg1 Switch: </label><input id="mg1Switch" type="text"><br><label for="mg2Genbus">Mg2 Gen Bus: </label><input id="mg2Genbus" type="text"><label for="mg2Switch"> Mg2 Switch: </label><input id="mg2Switch" type="text"><br><label for="mg3Genbus">Mg3 Gen Bus: </label><input id="mg3Genbus" type="text"><label for="mg3Switch"> Mg3 Switch: </label><input id="mg3Switch" type="text"><br></div><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 684_command_center</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 634a_data_center</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 634b_radar</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 634c_atc_tower</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 645_hangar</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 646_office</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 692_warehouse2</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 675a_hospital</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 675b_residential1</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 675c_residential1</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 611_runway</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 652_residential</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 670a_residential2</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 670b_residential2</label><br><label><select><option value="">None</option><option value="">Mg1</option><option value="">Mg2</option><option value="">Mg3</option></select> 670c_residential2</label><br></div>
`
function fillDropdownsLehigh() {
    $('#dropdowns').replaceWith(dropDowns);
}