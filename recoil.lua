EnablePrimaryMouseButtonEvents(true)
-- ================= 参数配置区 ================= --

-- 半自动步枪（侧键8）参数
local mb1_recoil_down = 14  -- 每次鼠标下移的像素距离
local mb1_recoil_delay = 10  -- 每次下移的间隔时间（毫秒）

-- 普通步枪（侧键6）参数
local mb8_recoil_down = 20   -- 每次鼠标下移的像素距离
local mb8_recoil_delay = 20  -- 每次下移的间隔时间（毫秒）

local fire_key = "end"
local press_delay = 10
-- ================= 核心代码区 ================= --
function OnEvent(event, arg)
    
    if event == "MOUSE_BUTTON_PRESSED" and arg == 1 then
        --Sleep(1)
        PressKey(fire_key)
        OutputLogMessage("Press button left\n")
    end
        
    if event == "MOUSE_BUTTON_RELEASED" and arg == 1 then
        --Sleep(1)
        ReleaseKey(fire_key)
        OutputLogMessage("Release button left\n")
    end
    if event == "MOUSE_BUTTON_PRESSED" and arg == 4 then
        OutputLogMessage("Press button 4\n")
    end
        
    if event == "MOUSE_BUTTON_RELEASED" and arg == 4 then
        OutputLogMessage("Release button 4\n")
    end

    if event == "MOUSE_BUTTON_PRESSED" and arg == 8 then
        OutputLogMessage("Press button 8\n")
        
        repeat 
            PressKey(fire_key)
            Sleep(press_delay)
            ReleaseKey(fire_key)
            Sleep(mb1_recoil_delay)
            MoveMouseRelative(0, mb1_recoil_down)
        until not IsMouseButtonPressed(1) 
    end
    
    if event == "MOUSE_BUTTON_RELEASED" and arg == 8 then
        OutputLogMessage("Release button 8\n")
    end

    if event == "MOUSE_BUTTON_PRESSED" and arg == 6 then 
        OutputLogMessage("Press button 6\n")
        PressKey(fire_key)
        
        -- 1. 开火前复原：初始化动态力度和计数器
        local current_recoil = mb8_recoil_down 
        local loop_count = 0 
        
        repeat 
            -- 使用动态力度进行压枪
            MoveMouseRelative(0, current_recoil)
            Sleep(mb8_recoil_delay)
            
            -- 2. 计数与力度递增逻辑
            loop_count = loop_count + 1
            if loop_count % 8 == 0 then      -- 如果循环次数是 8 的倍数
                current_recoil = current_recoil + 1 -- 压枪力度增加 1 个像素
            end
            
        until not IsMouseButtonPressed(1)
    end
    
    if event == "MOUSE_BUTTON_RELEASED" and arg == 6 then
        OutputLogMessage("Release button 6\n")
        ReleaseKey(fire_key)
    end

end